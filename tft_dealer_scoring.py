import json
import re
import statistics
from typing import Optional, Tuple
from pathlib import Path
ALLOWED_COSTS: Tuple[int, ...] = (1, 2, 3, 4, 5, 7)
COST_ANCHOR = {
    1: 35.0,
    2: 48.0,
    3: 62.0,
    4: 76.0,
    5: 88.0,
    7: 100.0,
}
COST_OVERRIDES = {
    "TFT16_Brock": 7,
    "TFT16_Zaahen": 7,
    "TFT16_BaronNashor": 7,
    "TFT16_Sylas": 7,
    "TFT16_AurelionSol": 7,
    "TFT16_Ryze": 7,
}


def resolve_default_champions_path() -> str:
    candidates = (
        Path("data/champions16_6.json"),
        Path("data/archive/16_5/champions16_5.json"),
        Path("champions.json"),
        Path("data/champions.json"),
    )
    for path in candidates:
        if path.exists():
            return str(path)
    raise FileNotFoundError(
        "No champions data file found. Expected one of: "
        "data/champions16_6.json, data/archive/16_5/champions16_5.json, champions.json, data/champions.json"
    )

def normalized_cost(champion: dict) -> Optional[int]:
    api_name = champion.get("apiName")
    if api_name in COST_OVERRIDES:
        return COST_OVERRIDES[api_name]
    return champion.get("cost")


# --- parsing helpers ---
TRIPLE_RE = re.compile(r"\[\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*\]")
TAG_BLOCK_RE = re.compile(
    r"<(?P<tag>magicDamage|physicalDamage|trueDamage|TFTBonus|scaleHealth)>(?P<body>.*?)</(?P=tag)>",
    re.DOTALL
)
COUNT_TRIPLE_RE = re.compile(r"(?!x)x")
COUNT_PLAIN_RE = re.compile(r"(?!x)x")
TARGET_TRIPLE_RE = re.compile(r"(?!x)x")
TARGET_PLAIN_RE = re.compile(r"(?!x)x")

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


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _percentile_rank(values, target: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return 1.0
    sorted_vals = sorted(values)
    less_or_equal = sum(1 for v in sorted_vals if v <= target)
    return (less_or_equal - 1) / (len(sorted_vals) - 1)


def _normalized_score(rows, row, metric_key: str) -> float:
    cost = row["cost"]
    cost_values = [float(r[metric_key]) for r in rows if r["cost"] == cost]
    global_values = [float(r[metric_key]) for r in rows]
    cost_pct = _percentile_rank(cost_values, float(row[metric_key]))
    global_pct = _percentile_rank(global_values, float(row[metric_key]))
    return 0.6 * cost_pct + 0.4 * global_pct


def _apply_monotonic_cost_median(rows, score_key: str, allowed_costs: Tuple[int, ...]) -> None:
    present_costs = [c for c in allowed_costs if any(r["cost"] == c for r in rows)]
    if not present_costs:
        return

    medians = {}
    for cost in present_costs:
        vals = [float(r[score_key]) for r in rows if r["cost"] == cost]
        medians[cost] = statistics.median(vals) if vals else 0.0

    target = {}
    running = float("-inf")
    for cost in present_costs:
        running = max(running, medians[cost])
        target[cost] = running

    for row in rows:
        row[score_key] = float(row[score_key]) + (target[row["cost"]] - medians[row["cost"]])


def _sum_second_values(text: str) -> float:
    return sum(float(m.group(2)) for m in TRIPLE_RE.finditer(text or ""))

def _extract_blocks(desc: str):
    for m in TAG_BLOCK_RE.finditer(desc or ""):
        yield m.group("tag"), m.group("body")


def _var2(variables, name: str, default: float = 0.0) -> float:
    for item in variables or []:
        if item.get("name") != name:
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


def _fallback_damage2(variables) -> float:
    values = [_var2(variables, key, 0.0) for key in FALLBACK_DAMAGE_KEYS]
    return max(values) if values else 0.0


def _desc_repeat_hint2(desc: str) -> float:
    vals = [float(m.group(1)) for m in COUNT_TRIPLE_RE.finditer(desc or "")]
    vals += [float(m.group(1)) for m in COUNT_PLAIN_RE.finditer(desc or "")]
    if not vals:
        return 1.0
    return max(1.0, max(vals))


def _desc_target_hint2(desc: str) -> float:
    vals = [float(m.group(1)) for m in TARGET_TRIPLE_RE.finditer(desc or "")]
    vals += [float(m.group(1)) for m in TARGET_PLAIN_RE.finditer(desc or "")]
    if not vals:
        return 1.0
    return max(1.0, max(vals))

def parse_skill_damage2_info(desc: str):
    dmg2 = 0.0
    damage_tag_count = 0
    triple_count = 0
    for tag, body in _extract_blocks(desc or ""):
        if tag in ("magicDamage", "physicalDamage", "trueDamage"):
            damage_tag_count += 1
            dmg2 += _sum_second_values(body)
            triple_count += len(TRIPLE_RE.findall(body))
    return {
        "damage2": dmg2,
        "damage_tag_count": float(damage_tag_count),
        "triple_count": float(triple_count),
        "has_damage_tag": float(1 if damage_tag_count > 0 else 0),
    }


def parse_skill_damage2(desc: str) -> float:
    return float(parse_skill_damage2_info(desc)["damage2"])


def estimate_spell_damage_profile(ch: dict, raw_tag_damage2: float, auto_dps_value: float):
    ability = ch.get("ability") or {}
    variables = ability.get("variables") or []
    desc = ability.get("desc") or ""
    stats = ch.get("stats") or {}

    fallback_base_damage2 = _fallback_damage2(variables)
    if raw_tag_damage2 > 0:
        base_damage2 = raw_tag_damage2
        base_source = "tag"
    elif fallback_base_damage2 > 0:
        base_damage2 = fallback_base_damage2
        base_source = "variable_fallback"
    else:
        base_damage2 = 0.0
        base_source = "none"

    projectile_count = max([1.0] + [_var2(variables, key, 0.0) for key in PROJECTILE_KEYS])
    repeat_count = max([1.0] + [_var2(variables, key, 0.0) for key in REPEAT_KEYS])
    summon_count = max([1.0] + [_var2(variables, key, 0.0) for key in SUMMON_KEYS])
    target_count_variable = max([1.0] + [_var2(variables, key, 0.0) for key in TARGET_KEYS])
    desc_repeat = _desc_repeat_hint2(desc)
    desc_targets = _desc_target_hint2(desc)

    if projectile_count <= 1.0 and repeat_count <= 1.0 and summon_count <= 1.0 and desc_repeat > 1.0:
        projectile_count = min(desc_repeat, 40.0)

    duration = _var2(variables, "Duration", 0.0)
    bonus_ad = _var2(variables, "BonusAD", 0.0)
    decaying_as = _var2(variables, "DecayingAttackSpeed", 0.0)
    mechanism_bonus2 = 0.0
    if duration > 0 and (bonus_ad > 0 or decaying_as > 0):
        bonus_term = bonus_ad + min(decaying_as, 4.0) * 0.30
        mechanism_bonus2 += auto_dps_value * bonus_term * duration

    extra_arrows = _var2(variables, "NumExtraArrows", 0.0)
    attack_speed = float(stats.get("attackSpeed") or 0.0)
    if duration > 0 and extra_arrows > 0 and base_damage2 > 0 and attack_speed > 0:
        mechanism_bonus2 += base_damage2 * extra_arrows * attack_speed * duration * 0.80

    total_cast_damage2 = base_damage2 * projectile_count * repeat_count * summon_count + mechanism_bonus2
    total_cast_damage2 = min(total_cast_damage2, 50000.0)
    target_count_used = max(1.0, target_count_variable, desc_targets)
    single_target_equiv2 = total_cast_damage2 / target_count_used

    return {
        "baseSource": base_source,
        "rawTagDamage2": max(0.0, raw_tag_damage2),
        "fallbackBaseDamage2": fallback_base_damage2,
        "baseDamage2Used": base_damage2,
        "mechanismBonus2": mechanism_bonus2,
        "totalCastDamage2": total_cast_damage2,
        "singleTargetEquiv2": single_target_equiv2,
        "targetCountUsed": target_count_used,
        "projectileCount": projectile_count,
        "repeatCount": repeat_count,
        "summonCount": summon_count,
        "descRepeatHint2": desc_repeat,
        "descTargetHint2": desc_targets,
    }

def auto_dps(stats: dict) -> float:
    ad = float(stats.get("damage") or 0.0)
    asp = float(stats.get("attackSpeed") or 0.0)
    cc = float(stats.get("critChance") or 0.0)
    cm = float(stats.get("critMultiplier") or 1.0)
    return ad * asp * (1.0 + cc * max(0.0, cm - 1.0))

# --- mana rules from your OCR note (+ set16 roles) ---
ROLE_MANA = {
    "ADCarry": {"mana_on_attack": 10, "mana_regen": 0},
    "APCarry": {"mana_on_attack": 10, "mana_regen": 0},
    "ADFighter": {"mana_on_attack": 10, "mana_regen": 0},
    "APFighter": {"mana_on_attack": 10, "mana_regen": 0},
    "HFighter": {"mana_on_attack": 10, "mana_regen": 0},
    "ADReaper": {"mana_on_attack": 10, "mana_regen": 0},   # 由ы띁???꾩궗/?붿궡?먯쿂??痍④툒
    "APReaper": {"mana_on_attack": 10, "mana_regen": 0},
    "APCaster": {"mana_on_attack": 7, "mana_regen": 2},
    "ADCaster": {"mana_on_attack": 7, "mana_regen": 2},
    "ADCasterFormSwapper": {"mana_on_attack": 7, "mana_regen": 2},
    "ADSpecialist": {"mana_on_attack": 10, "mana_regen": 0},
    "APSpecialist": {"mana_on_attack": 7, "mana_regen": 2},
}

def mps(role: str, attack_speed: float) -> float:
    rule = ROLE_MANA.get(role, {"mana_on_attack": 10, "mana_regen": 0})
    return attack_speed * rule["mana_on_attack"] + rule["mana_regen"]

def dealer_score_row(ch, fight_window=10.0,
                     ad_auto_w=1.0, ad_spell_w=0.35,
                     ap_spell_w=1.0, ap_auto_w=0.25):
    stats = ch.get("stats") or {}
    role = ch.get("role")
    desc = (ch.get("ability") or {}).get("desc", "") or ""

    aDPS = auto_dps(stats)
    parse_info = parse_skill_damage2_info(desc)
    raw_tag_damage2 = float(parse_info["damage2"])
    spell_profile = estimate_spell_damage_profile(ch, raw_tag_damage2, aDPS)
    dmg2 = float(spell_profile["singleTargetEquiv2"])

    asp = float(stats.get("attackSpeed") or 0.0)
    mana = float(stats.get("mana") or 0.0)
    init = float(stats.get("initialMana") or 0.0)

    MPS = mps(role, asp)
    mana_needed = max(0.0, mana - init)
    t_first = mana_needed / (MPS if MPS > 1e-9 else 1e-9)
    readiness = fight_window / (fight_window + t_first) if (fight_window + t_first) > 0 else 1.0

    casts_per_sec = (MPS / mana) if (mana > 1e-9 and MPS > 1e-9) else 0.0
    spell_dps_hint = dmg2 * casts_per_sec * readiness

    # bucket by role (AD-like vs AP-like aggregation)
    is_ad_like = isinstance(role, str) and (role.startswith("AD") or role == "HFighter")
    if is_ad_like:
        sustain_dps = aDPS * 0.65 + spell_dps_hint * 0.35
    else:
        sustain_dps = aDPS * 0.35 + spell_dps_hint * 0.65
    burst_dps_equiv = dmg2 / max(t_first + 1.0, 1.0)

    return {
        "cost": ch.get("cost"),
        "name": ch.get("name"),
        "apiName": ch.get("apiName"),
        "role": role,
        "score": 0.0,
        "autoDPS": round(aDPS, 2),
        "spellDPS_hint": round(spell_dps_hint, 2),
        "skillDamage2": round(dmg2, 2),
        "rawTagDamage2": round(float(spell_profile["rawTagDamage2"]), 2),
        "totalCastDamage2": round(float(spell_profile["totalCastDamage2"]), 2),
        "targetCountUsed": round(float(spell_profile["targetCountUsed"]), 2),
        "fallbackBaseDamage2": round(float(spell_profile["fallbackBaseDamage2"]), 2),
        "baseDamage2Used": round(float(spell_profile["baseDamage2Used"]), 2),
        "mechanismBonus2": round(float(spell_profile["mechanismBonus2"]), 2),
        "tFirstCast": round(t_first, 2),
        "readiness": round(readiness, 3),
        "raw_sustain_dps": sustain_dps,
        "raw_burst_dps": burst_dps_equiv,
        "raw_cast_stability": readiness,
        "raw_auto_pressure": aDPS,
        "confidence_raw": _clamp(
            0.35
            + (0.20 if parse_info["has_damage_tag"] else 0.0)
            + 0.20 * min(1.0, parse_info["triple_count"] / 3.0)
            + 0.10 * min(1.0, parse_info["damage_tag_count"] / 2.0)
            + (0.10 if float(spell_profile["baseDamage2Used"]) > 0 else 0.0)
            + (0.05 if float(spell_profile["mechanismBonus2"]) > 0 else 0.0)
            + (0.05 if mana > 0 and asp > 0 else 0.0)
            + (0.05 if (ch.get("traits") or []) else 0.0),
            0.20,
            0.95,
        ),
    }

def score_all_dealers(
    champions_json_path: str,
    min_cost: Optional[int] = None,
    max_cost: Optional[int] = None,
    include_costs: Optional[Tuple[int, ...]] = ALLOWED_COSTS,
    roles: Optional[Tuple[str, ...]] = None,
    exclude_traitless: bool = True,
):
    with open(champions_json_path, "r", encoding="utf-8") as f:
        root = json.load(f)
    champs = root.get("data", root)
    if roles is None:
        roles = tuple(
            sorted({
                ch.get("role")
                for ch in champs
                if isinstance(ch.get("role"), str) and not ch.get("role", "").endswith("Tank")
            })
        )

    out = []
    for ch in champs:
        cost = normalized_cost(ch)
        role = ch.get("role")
        traits = ch.get("traits") or []
        if exclude_traitless and not traits:
            continue
        if min_cost is not None and (cost is None or cost < min_cost):
            continue
        if max_cost is not None and (cost is None or cost > max_cost):
            continue
        if include_costs is not None and cost not in include_costs:
            continue
        if role not in roles:
            continue
        ch_for_row = ch if ch.get("cost") == cost else {**ch, "cost": cost}
        out.append(dealer_score_row(ch_for_row))

    for row in out:
        sustain_norm = _normalized_score(out, row, "raw_sustain_dps")
        burst_norm = _normalized_score(out, row, "raw_burst_dps")
        cast_norm = _normalized_score(out, row, "raw_cast_stability")
        auto_norm = _normalized_score(out, row, "raw_auto_pressure")
        final_score = 100.0 * (
            0.40 * sustain_norm
            + 0.30 * burst_norm
            + 0.20 * cast_norm
            + 0.10 * auto_norm
        )
        efficiency_score = final_score
        cost_anchor = COST_ANCHOR.get(int(row["cost"]), 50.0)
        power_score = 0.35 * efficiency_score + 0.65 * cost_anchor
        row["efficiencyScore"] = round(efficiency_score, 2)
        row["powerScore"] = round(power_score, 2)
        row["score"] = round(power_score, 2)
        row["confidence"] = round(float(row["confidence_raw"]), 2)
        row["subscores"] = {
            "sustain_dps": round(sustain_norm * 100.0, 1),
            "burst_window": round(burst_norm * 100.0, 1),
            "cast_stability": round(cast_norm * 100.0, 1),
            "auto_pressure": round(auto_norm * 100.0, 1),
        }

    _apply_monotonic_cost_median(out, "score", ALLOWED_COSTS)
    for row in out:
        row["score"] = round(float(row["score"]), 2)

    for row in out:
        del row["raw_sustain_dps"]
        del row["raw_burst_dps"]
        del row["raw_cast_stability"]
        del row["raw_auto_pressure"]
        del row["confidence_raw"]

    out.sort(key=lambda x: x["score"], reverse=True)
    return out

# Example
if __name__ == "__main__":
    input_path = resolve_default_champions_path()
    dealers = score_all_dealers(
        input_path,
        min_cost=None,
        max_cost=None,
        include_costs=ALLOWED_COSTS,
        roles=None,
        exclude_traitless=True,
    )
    output = {"total": len(dealers), "results": dealers}
    output_path = "tft_dealer_scoring_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Input: {input_path}")
    print(f"Saved {output['total']} dealer rows to {output_path}")

