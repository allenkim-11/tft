import json
import re
import statistics
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path

# ----------------------------
# Utils
# ----------------------------

TRIPLE_RE = re.compile(r"\[\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*\]")
TAG_BLOCK_RE = re.compile(r"<(?P<tag>magicDamage|physicalDamage|trueDamage|TFTBonus|scaleHealth)>(?P<body>.*?)</(?P=tag)>", re.DOTALL)
COUNT_TRIPLE_RE = re.compile(r"(?!x)x")
COUNT_PLAIN_RE = re.compile(r"(?!x)x")
TARGET_TRIPLE_RE = re.compile(r"(?!x)x")
TARGET_PLAIN_RE = re.compile(r"(?!x)x")
ALLOWED_COSTS: Tuple[int, ...] = (1, 2, 3, 4, 5, 7)
COST_ANCHOR: Dict[int, float] = {
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

def normalized_cost(champion: Dict[str, Any]) -> Optional[int]:
    api_name = champion.get("apiName")
    if api_name in COST_OVERRIDES:
        return COST_OVERRIDES[api_name]
    return champion.get("cost")

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


def _percentile_rank(values: List[float], target: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return 1.0
    sorted_vals = sorted(values)
    less_or_equal = sum(1 for v in sorted_vals if v <= target)
    return (less_or_equal - 1) / (len(sorted_vals) - 1)


def _normalized_score(rows: List[Dict[str, Any]], row: Dict[str, Any], metric_key: str) -> float:
    cost = row["cost"]
    cost_values = [float(r[metric_key]) for r in rows if r["cost"] == cost]
    global_values = [float(r[metric_key]) for r in rows]
    cost_pct = _percentile_rank(cost_values, float(row[metric_key]))
    global_pct = _percentile_rank(global_values, float(row[metric_key]))
    return 0.6 * cost_pct + 0.4 * global_pct


def _var2(variables: List[Dict[str, Any]], name: str, default: float = 0.0) -> float:
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


def _fallback_damage2(variables: List[Dict[str, Any]]) -> float:
    values = [_var2(variables, key, 0.0) for key in FALLBACK_DAMAGE_KEYS]
    return max(values) if values else 0.0


def _desc_repeat_hint2(desc: str) -> float:
    values = [float(m.group(1)) for m in COUNT_TRIPLE_RE.finditer(desc or "")]
    values += [float(m.group(1)) for m in COUNT_PLAIN_RE.finditer(desc or "")]
    if not values:
        return 1.0
    return max(1.0, max(values))


def _desc_target_hint2(desc: str) -> float:
    values = [float(m.group(1)) for m in TARGET_TRIPLE_RE.finditer(desc or "")]
    values += [float(m.group(1)) for m in TARGET_PLAIN_RE.finditer(desc or "")]
    if not values:
        return 1.0
    return max(1.0, max(values))


def estimate_spell_damage_profile(champion: Dict[str, Any], raw_tag_damage2: float) -> Dict[str, float]:
    ability = champion.get("ability") or {}
    variables = ability.get("variables") or []
    desc = ability.get("desc") or ""
    stats = champion.get("stats") or {}

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

    attack_speed = float(stats.get("attackSpeed") or 0.0)
    attack_damage = float(stats.get("damage") or 0.0)
    auto_dps = attack_speed * attack_damage
    duration = _var2(variables, "Duration", 0.0)
    bonus_ad = _var2(variables, "BonusAD", 0.0)
    decaying_as = _var2(variables, "DecayingAttackSpeed", 0.0)
    extra_arrows = _var2(variables, "NumExtraArrows", 0.0)

    mechanism_bonus2 = 0.0
    if duration > 0 and (bonus_ad > 0 or decaying_as > 0):
        bonus_term = bonus_ad + min(decaying_as, 4.0) * 0.30
        mechanism_bonus2 += auto_dps * bonus_term * duration
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


def _apply_monotonic_cost_median(rows: List[Dict[str, Any]], score_key: str, allowed_costs: Tuple[int, ...]) -> None:
    present_costs = [c for c in allowed_costs if any(r["cost"] == c for r in rows)]
    if not present_costs:
        return

    medians: Dict[int, float] = {}
    for cost in present_costs:
        vals = [float(r[score_key]) for r in rows if r["cost"] == cost]
        medians[cost] = statistics.median(vals) if vals else 0.0

    target_median: Dict[int, float] = {}
    running = float("-inf")
    for cost in present_costs:
        running = max(running, medians[cost])
        target_median[cost] = running

    for row in rows:
        delta = target_median[row["cost"]] - medians[row["cost"]]
        row[score_key] = float(row[score_key]) + delta

def _sum_second_values_in_text(text: str) -> float:
    """Sum the 2-star (middle) values from all [x / y / z] triples found in text."""
    total = 0.0
    for m in TRIPLE_RE.finditer(text):
        total += float(m.group(2))
    return total

def _extract_tag_blocks(desc: str) -> List[Tuple[str, str, int, int]]:
    """Return list of (tag, body, start, end) for each <tag>...</tag> block."""
    out = []
    for m in TAG_BLOCK_RE.finditer(desc or ""):
        out.append((m.group("tag"), m.group("body"), m.start(), m.end()))
    return out

def _near_has_keyword(desc: str, start: int, end: int, keyword: str, window: int = 80) -> bool:
    """Check if a keyword exists near a tag block (within +/- window chars)."""
    lo = max(0, start - window)
    hi = min(len(desc), end + window)
    return keyword in desc[lo:hi]

# ----------------------------
# Skill parsing (damage / shield / heal)
# ----------------------------

def parse_tank_skill_components(desc: str) -> Dict[str, float]:
    """
    Parse ability.desc into components (2-star values):
      - damage2: sum of [x/y/z] in magicDamage/physicalDamage/trueDamage blocks
      - shield2: sum of [x/y/z] in TFTBonus blocks near keyword '蹂댄샇留?
      - heal2:   sum of [x/y/z] in scaleHealth blocks near keyword '?뚮났'
    """
    damage2 = 0.0
    shield2 = 0.0
    heal2 = 0.0

    blocks = _extract_tag_blocks(desc or "")

    for tag, body, s, e in blocks:
        if tag in ("magicDamage", "physicalDamage", "trueDamage"):
            damage2 += _sum_second_values_in_text(body)
        elif tag == "TFTBonus":
            # Treat TFTBonus as shield only when near "蹂댄샇留?
            if _near_has_keyword(desc, s, e, "\ubcf4\ud638\ub9c9"):
                shield2 += _sum_second_values_in_text(body)
        elif tag == "scaleHealth":
            # Treat scaleHealth as heal only when near "?뚮났"
            if _near_has_keyword(desc, s, e, "\ud68c\ubcf5"):
                heal2 += _sum_second_values_in_text(body)

    damage_tag_count = 0
    bonus_tag_count = 0
    scale_health_tag_count = 0
    triple_count = 0
    for tag, body, _, _ in blocks:
        if tag in ("magicDamage", "physicalDamage", "trueDamage"):
            damage_tag_count += 1
        elif tag == "TFTBonus":
            bonus_tag_count += 1
        elif tag == "scaleHealth":
            scale_health_tag_count += 1
        triple_count += len(TRIPLE_RE.findall(body))

    return {
        "damage2": damage2,
        "shield2": shield2,
        "heal2": heal2,
        "damage_tag_count": float(damage_tag_count),
        "bonus_tag_count": float(bonus_tag_count),
        "scale_health_tag_count": float(scale_health_tag_count),
        "triple_count": float(triple_count),
        "has_any_tag": float(1 if len(blocks) > 0 else 0),
    }

# ----------------------------
# Tank score formula
# ----------------------------

def tank_score(
    hp: float,
    armor: float,
    mr: float,
    attack_speed: float,
    mana: float,
    initial_mana: float,
    damage2: float = 0.0,
    shield2: float = 0.0,
    heal2: float = 0.0,
    hit_const: float = 3.0,   # ?깆빱 ?쇨꺽 留덈굹 怨듯넻 ?곸닔(珥덈떦)
    W: float = 6.0,           # 珥덈컲 援먯쟾 李?珥?
    off_weight: float = 0.15  # ?깆빱 泥닿툒?먯꽌 ??媛以묒튂
) -> Dict[str, float]:
    """
    TankScore = BaseEHP + ((shield2+heal2)*avgMit + damage2*off_weight) * readiness
    readiness = W / (W + t_cast)
    t_cast = (mana - initialMana) / (attack_speed*5 + hit_const)
    """
    phys_mit = 1.0 + (armor / 100.0)
    mag_mit = 1.0 + (mr / 100.0)
    avg_mit = (phys_mit + mag_mit) / 2.0

    base_ehp = hp * avg_mit

    mps = attack_speed * 5.0 + hit_const
    # guard
    mana_needed = max(0.0, mana - initial_mana)
    t_cast = mana_needed / max(mps, 1e-6)

    readiness = W / (W + t_cast) if (W + t_cast) > 0 else 1.0

    def_value = (shield2 + heal2) * avg_mit
    off_value = damage2 * off_weight

    score = base_ehp + (def_value + off_value) * readiness

    return {
        "score": score,
        "baseEHP": base_ehp,
        "avgMit": avg_mit,
        "mps": mps,
        "tcast": t_cast,
        "readiness": readiness,
        "damage2": damage2,
        "shield2": shield2,
        "heal2": heal2,
    }

# ----------------------------
# Run on champions.json
# ----------------------------

def score_all_tanks(
    champions_json_path: str,
    min_cost: Optional[int] = None,
    max_cost: Optional[int] = None,
    include_costs: Optional[Tuple[int, ...]] = ALLOWED_COSTS,
    include_roles: Optional[Tuple[str, ...]] = None,
    exclude_traitless: bool = True,
    hit_const: float = 3.0,
    W: float = 6.0,
    off_weight: float = 0.15,
) -> List[Dict[str, Any]]:
    """
    Loads champions.json and scores all tanks.
    Defaults are set to include all tank roles and costs in ALLOWED_COSTS.
    Returns list of dicts sorted by score desc.
    """
    with open(champions_json_path, "r", encoding="utf-8") as f:
        root = json.load(f)

    data = root.get("data", root)  # tolerate raw list
    if include_roles is None:
        include_roles = tuple(
            sorted({
                ch.get("role")
                for ch in data
                if isinstance(ch.get("role"), str) and ch.get("role", "").endswith("Tank")
            })
        )

    results = []
    for ch in data:
        cost = normalized_cost(ch)
        role = ch.get("role", None)
        traits = ch.get("traits", [])
        if role is None:
            continue
        if min_cost is not None and (cost is None or cost < min_cost):
            continue
        if max_cost is not None and (cost is None or cost > max_cost):
            continue
        if include_costs is not None and cost not in include_costs:
            continue
        if role not in include_roles:
            continue
        if exclude_traitless and (not traits):
            # filter out special objects (traitless)
            continue

        stats = ch.get("stats", {}) or {}
        hp = float(stats.get("hp") or 0.0)
        armor = float(stats.get("armor") or 0.0)
        mr = float(stats.get("magicResist") or 0.0)
        attack_speed = float(stats.get("attackSpeed") or 0.0)
        mana = float(stats.get("mana") or 0.0)
        initial_mana = float(stats.get("initialMana") or 0.0)

        ability = ch.get("ability", {}) or {}
        desc = ability.get("desc", "") or ""

        comps = parse_tank_skill_components(desc)
        spell_profile = estimate_spell_damage_profile(ch, comps["damage2"])
        damage2_for_score = float(spell_profile["singleTargetEquiv2"])
        out = tank_score(
            hp=hp, armor=armor, mr=mr,
            attack_speed=attack_speed,
            mana=mana, initial_mana=initial_mana,
            damage2=damage2_for_score,
            shield2=comps["shield2"],
            heal2=comps["heal2"],
            hit_const=hit_const,
            W=W,
            off_weight=off_weight
        )

        results.append({
            "cost": cost,
            "name": ch.get("name"),
            "apiName": ch.get("apiName"),
            "role": role,
            "rawTagDamage2": round(float(spell_profile["rawTagDamage2"]), 2),
            "totalCastDamage2": round(float(spell_profile["totalCastDamage2"]), 2),
            "targetCountUsed": round(float(spell_profile["targetCountUsed"]), 2),
            "fallbackBaseDamage2": round(float(spell_profile["fallbackBaseDamage2"]), 2),
            "baseDamage2Used": round(float(spell_profile["baseDamage2Used"]), 2),
            "mechanismBonus2": round(float(spell_profile["mechanismBonus2"]), 2),
            "confidence_raw": _clamp(
                0.35
                + (0.15 if comps["has_any_tag"] else 0.0)
                + 0.15 * min(1.0, comps["triple_count"] / 3.0)
                + 0.15 * min(1.0, (comps["damage_tag_count"] + comps["bonus_tag_count"] + comps["scale_health_tag_count"]) / 3.0)
                + (0.10 if (damage2_for_score + comps["shield2"] + comps["heal2"]) > 0 else 0.0)
                + (0.05 if float(spell_profile["mechanismBonus2"]) > 0 else 0.0)
                + (0.05 if mana > 0 and attack_speed > 0 else 0.0)
                + (0.05 if traits else 0.0),
                0.20,
                0.95,
            ),
            "raw_base_ehp": out["baseEHP"],
            "raw_defense_value": (comps["shield2"] + comps["heal2"]) * out["avgMit"] * out["readiness"],
            "raw_offense_value": damage2_for_score * off_weight * out["readiness"],
            "raw_cast_stability": out["readiness"],
            **out
        })

    for row in results:
        base_norm = _normalized_score(results, row, "raw_base_ehp")
        defense_norm = _normalized_score(results, row, "raw_defense_value")
        offense_norm = _normalized_score(results, row, "raw_offense_value")
        cast_norm = _normalized_score(results, row, "raw_cast_stability")
        final_score = 100.0 * (
            0.45 * base_norm
            + 0.30 * defense_norm
            + 0.15 * cast_norm
            + 0.10 * offense_norm
        )
        efficiency_score = final_score
        cost_anchor = COST_ANCHOR.get(int(row["cost"]), 50.0)
        power_score = 0.35 * efficiency_score + 0.65 * cost_anchor
        row["efficiencyScore"] = round(efficiency_score, 2)
        row["powerScore"] = round(power_score, 2)
        row["score"] = round(power_score, 2)
        row["confidence"] = round(float(row["confidence_raw"]), 2)
        row["subscores"] = {
            "base_ehp": round(base_norm * 100.0, 1),
            "defense_utility": round(defense_norm * 100.0, 1),
            "cast_stability": round(cast_norm * 100.0, 1),
            "offense": round(offense_norm * 100.0, 1),
        }

    _apply_monotonic_cost_median(results, "score", ALLOWED_COSTS)
    for row in results:
        row["score"] = round(float(row["score"]), 2)

    for row in results:
        del row["confidence_raw"]
        del row["raw_base_ehp"]
        del row["raw_defense_value"]
        del row["raw_offense_value"]
        del row["raw_cast_stability"]

    results.sort(key=lambda x: x["score"], reverse=True)
    return results

if __name__ == "__main__":
    path = resolve_default_champions_path()
    tanks = score_all_tanks(
        champions_json_path=path,
        min_cost=None,
        max_cost=None,
        include_costs=ALLOWED_COSTS,
        include_roles=None,
        exclude_traitless=True,
        hit_const=3.0,
        W=6.0,
        off_weight=0.15
    )

    output = {"total": len(tanks), "results": tanks}
    output_path = "tank_scoring_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Input: {path}")
    print(f"Saved {output['total']} tank rows to {output_path}")


