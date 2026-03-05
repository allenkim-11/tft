import json
import re
from typing import Any, Dict, List, Tuple

ALLOWED_COSTS = {1, 2, 3, 4, 5, 7}

DAMAGE_TAG_RE = re.compile(
    r"<(?P<tag>magicDamage|physicalDamage|trueDamage)>(?P<body>.*?)</(?P=tag)>",
    re.DOTALL,
)
TRIPLE_RE = re.compile(
    r"\[\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*\]"
)
COUNT_TRIPLE_RE = re.compile(
    r"(?:<scaleLevel>)?\[\s*[0-9]+(?:\.[0-9]+)?\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*[0-9]+(?:\.[0-9]+)?\s*\](?:</scaleLevel>)?\s*(개|회|발|타|번)"
)
COUNT_PLAIN_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(개|회|발|타|번)")
TARGET_TRIPLE_RE = re.compile(
    r"적\s*(?:최대\s*)?(?:<scaleLevel>)?\[\s*[0-9]+(?:\.[0-9]+)?\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*[0-9]+(?:\.[0-9]+)?\s*\](?:</scaleLevel>)?\s*명"
)
TARGET_PLAIN_RE = re.compile(r"적\s*(?:최대\s*)?([0-9]+(?:\.[0-9]+)?)\s*명")

PROJECTILE_KEYS = (
    "NumMeteors",
    "NumMissiles",
    "NumProjectiles",
    "NumBolts",
    "NumArrows",
    "NumShots",
    "NumStrikes",
    "NumSpears",
    "TotalNumberOfSpears",
    "NumExtraArrows",
)
REPEAT_KEYS = ("NumAttacks", "NumHits", "HitCount")
SUMMON_KEYS = ("NumMinions", "NumPets", "NumSpawned")
TARGET_KEYS = ("NumTargets", "MaxTargets", "TargetCount", "NumEnemiesToFocusFire", "NumberOfEnemies")
FALLBACK_DAMAGE_KEYS = ("ModifiedDamage", "Damage", "ADDamage", "APDamage")


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def var2(variables: List[Dict[str, Any]], key: str, default: float = 0.0) -> float:
    for item in variables:
        if item.get("name") != key:
            continue
        value = item.get("value")
        if isinstance(value, list):
            if len(value) > 1 and isinstance(value[1], (int, float)):
                return float(value[1])
            if len(value) > 0 and isinstance(value[0], (int, float)):
                return float(value[0])
        if isinstance(value, (int, float)):
            return float(value)
    return default


def sum_tag_damage2(desc: str) -> Tuple[float, int]:
    total = 0.0
    tag_count = 0
    for match in DAMAGE_TAG_RE.finditer(desc or ""):
        tag_count += 1
        body = match.group("body")
        for triple in TRIPLE_RE.finditer(body):
            total += float(triple.group(2))
    return total, tag_count


def fallback_damage2(variables: List[Dict[str, Any]]) -> float:
    values = [var2(variables, key, 0.0) for key in FALLBACK_DAMAGE_KEYS]
    return max(values) if values else 0.0


def desc_repeat_hint2(desc: str) -> float:
    candidates: List[float] = []
    for m in COUNT_TRIPLE_RE.finditer(desc or ""):
        candidates.append(float(m.group(1)))
    # plain pattern is fallback only; can capture noise so it is capped later.
    for m in COUNT_PLAIN_RE.finditer(desc or ""):
        candidates.append(float(m.group(1)))
    if not candidates:
        return 1.0
    return max(1.0, max(candidates))


def desc_target_hint2(desc: str) -> float:
    candidates: List[float] = []
    for m in TARGET_TRIPLE_RE.finditer(desc or ""):
        candidates.append(float(m.group(1)))
    for m in TARGET_PLAIN_RE.finditer(desc or ""):
        candidates.append(float(m.group(1)))
    if not candidates:
        return 1.0
    return max(1.0, max(candidates))


def build_row(champion: Dict[str, Any]) -> Dict[str, Any]:
    ability = champion.get("ability") or {}
    desc = ability.get("desc") or ""
    variables = ability.get("variables") or []
    stats = champion.get("stats") or {}

    raw_tag_damage2, damage_tag_count = sum_tag_damage2(desc)
    fallback_base_damage2 = fallback_damage2(variables)
    if raw_tag_damage2 > 0:
        base_damage2 = raw_tag_damage2
        base_source = "tag"
    elif fallback_base_damage2 > 0:
        base_damage2 = fallback_base_damage2
        base_source = "variable_fallback"
    else:
        base_damage2 = 0.0
        base_source = "none"

    projectile_count = max([1.0] + [var2(variables, key, 0.0) for key in PROJECTILE_KEYS])
    repeat_count = max([1.0] + [var2(variables, key, 0.0) for key in REPEAT_KEYS])
    summon_count = max([1.0] + [var2(variables, key, 0.0) for key in SUMMON_KEYS])
    variable_target_count = max([1.0] + [var2(variables, key, 0.0) for key in TARGET_KEYS])

    desc_repeat = desc_repeat_hint2(desc)
    desc_targets = desc_target_hint2(desc)

    # Keep description hints as lower-priority fallback to avoid runaway overcount.
    if projectile_count <= 1.0 and repeat_count <= 1.0 and summon_count <= 1.0 and desc_repeat > 1.0:
        projectile_count = min(desc_repeat, 40.0)

    # Mechanism-aware adjustment for kits where direct tag damage is understated.
    attack_speed = float(stats.get("attackSpeed") or 0.0)
    attack_damage = float(stats.get("damage") or 0.0)
    auto_dps = attack_speed * attack_damage
    duration = var2(variables, "Duration", 0.0)
    bonus_ad = var2(variables, "BonusAD", 0.0)
    decaying_as = var2(variables, "DecayingAttackSpeed", 0.0)
    extra_arrows = var2(variables, "NumExtraArrows", 0.0)

    mechanism_bonus2 = 0.0
    if duration > 0.0 and (bonus_ad > 0.0 or decaying_as > 0.0):
        buff_term = bonus_ad + min(decaying_as, 4.0) * 0.30
        mechanism_bonus2 += auto_dps * buff_term * duration

    if duration > 0.0 and extra_arrows > 0.0 and base_damage2 > 0.0 and attack_speed > 0.0:
        extra_hits = extra_arrows * attack_speed * duration
        mechanism_bonus2 += base_damage2 * extra_hits * 0.80

    total_cast_damage2 = base_damage2 * projectile_count * repeat_count * summon_count + mechanism_bonus2
    total_cast_damage2 = min(total_cast_damage2, 50000.0)
    target_count = max(1.0, variable_target_count, desc_targets)
    single_target_equiv2 = total_cast_damage2 / target_count

    confidence = clamp(
        0.30
        + (0.25 if damage_tag_count > 0 else 0.0)
        + (0.15 if base_source == "variable_fallback" else 0.0)
        + 0.10 * min(1.0, (projectile_count - 1.0) / 10.0)
        + 0.10 * min(1.0, (repeat_count - 1.0) / 10.0)
        + 0.05 * min(1.0, (summon_count - 1.0) / 5.0)
        + (0.05 if mechanism_bonus2 > 0.0 else 0.0)
        + (0.05 if target_count > 1.0 else 0.0),
        0.20,
        0.95,
    )

    return {
        "apiName": champion.get("apiName"),
        "name": champion.get("name"),
        "cost": champion.get("cost"),
        "role": champion.get("role"),
        "rawTagDamage2": round(raw_tag_damage2, 2),
        "fallbackBaseDamage2": round(fallback_base_damage2, 2),
        "baseDamage2Used": round(base_damage2, 2),
        "mechanismBonus2": round(mechanism_bonus2, 2),
        "totalCastDamage2": round(total_cast_damage2, 2),
        "singleTargetEquiv2": round(single_target_equiv2, 2),
        "targetCountUsed": round(target_count, 2),
        "multipliers": {
            "projectile": round(projectile_count, 2),
            "repeat": round(repeat_count, 2),
            "summon": round(summon_count, 2),
            "duration": round(duration, 2),
            "bonusAD": round(bonus_ad, 2),
            "decayingAS": round(decaying_as, 2),
            "extraArrows": round(extra_arrows, 2),
            "descRepeatHint2": round(desc_repeat, 2),
            "descTargetHint2": round(desc_targets, 2),
        },
        "meta": {
            "baseSource": base_source,
            "damageTagCount": damage_tag_count,
            "confidence": round(confidence, 2),
        },
    }


def main() -> None:
    with open("champions.json", "r", encoding="utf-8") as f:
        root = json.load(f)
    champions = root.get("data", root)

    rows = []
    for ch in champions:
        cost = ch.get("cost")
        role = ch.get("role")
        if not isinstance(cost, int) or cost not in ALLOWED_COSTS:
            continue
        if not role:
            continue
        rows.append(build_row(ch))

    rows.sort(key=lambda r: (r["cost"], r["role"], -r["singleTargetEquiv2"]))
    output = {"total": len(rows), "results": rows}
    out_path = "champion_spell_damage_audit.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Saved {output['total']} rows to {out_path}")


if __name__ == "__main__":
    main()
