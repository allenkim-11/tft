import argparse
import ast
import json
import re
from difflib import SequenceMatcher
from pathlib import Path


TOKEN_RE = re.compile(r"@([^@]+)@")
SIMPLE_PREFIXES = ("Modified", "Total", "Reduced", "FirstCast", "SecondCast", "ThirdCast")
SIMPLE_SUFFIXES = ("Final",)
FORMULA_SUFFIX_RE = re.compile(r"^([A-Za-z0-9_:.]+)\*(100|10)%?$")
DEFAULT_STAR_INDEXES = (1, 2, 3)


def normalize(value: str) -> str:
    value = value or ""
    value = value.replace("TFTUnitProperty.:", "")
    value = value.replace("MustMatch", "")
    value = value.replace("_MustMatch", "")
    value = value.replace("%", "")
    value = value.replace("*100", "")
    value = value.replace("*10", "")
    value = value.replace("*", "")
    value = value.replace(".", "")
    value = value.replace(":", "")
    value = value.replace("_", "")
    value = value.lower()
    for prefix in ("modified", "total", "reduced", "firstcast", "secondcast", "thirdcast"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
    for suffix in ("final",):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    return value


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def extract_tokens(desc: str) -> list[str]:
    return sorted(set(TOKEN_RE.findall(desc or "")))


def replace_tokens_in_desc(desc: str, token_to_expr: dict[str, str]) -> str:
    def _replace(match: re.Match) -> str:
        token = match.group(1)
        expr = token_to_expr.get(token)
        if expr is None:
            return f"{{UNRESOLVED:{token}}}"
        return f"{{{expr}}}"

    return TOKEN_RE.sub(_replace, desc or "")


def insert_desc_resolved_field(ability: dict, resolved_desc: str) -> dict:
    updated: dict = {}
    inserted = False

    for key, value in ability.items():
        updated[key] = value
        if key == "desc":
            updated["descResolved"] = resolved_desc
            inserted = True

    if not inserted:
        updated["descResolved"] = resolved_desc

    return updated


def parse_star_indexes(raw: str) -> tuple[int, ...]:
    values = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        values.append(int(part))
    if not values:
        return DEFAULT_STAR_INDEXES
    return tuple(values)


def to_float(value):
    if isinstance(value, (int, float)):
        return float(value)
    return None


def pick_star_values(raw_values, star_indexes: tuple[int, ...]):
    if not isinstance(raw_values, list):
        return None

    selected = []
    for idx in star_indexes:
        if 0 <= idx < len(raw_values):
            selected.append(to_float(raw_values[idx]))
        else:
            selected.append(None)

    if any(v is not None for v in selected):
        return [0.0 if v is None else v for v in selected]

    fallback = [to_float(v) for v in raw_values if to_float(v) is not None]
    if not fallback:
        return None

    if len(fallback) >= len(star_indexes):
        return fallback[: len(star_indexes)]

    while len(fallback) < len(star_indexes):
        fallback.append(fallback[-1])
    return fallback


def build_value_context(champ: dict, star_indexes: tuple[int, ...]):
    ability = champ.get("ability") or {}
    var_values = {}
    for row in ability.get("variables") or []:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        if not name:
            continue
        vec = pick_star_values(row.get("value"), star_indexes)
        if vec is None:
            vec = [0.0] * len(star_indexes)
        var_values[name] = vec

    stats = champ.get("stats") or {}
    stat_values = {}
    for key, value in stats.items():
        fv = to_float(value)
        if fv is None:
            continue
        stat_values[key] = fv
        stat_values[key.lower()] = fv

    return var_values, stat_values


def tokenize_expression(expr: str):
    tokens = []
    i = 0
    while i < len(expr):
        ch = expr[i]

        if ch.isspace():
            i += 1
            continue

        if ch in "+-*/()":
            tokens.append(("op", ch))
            i += 1
            continue

        if ch.isdigit() or (ch == "." and i + 1 < len(expr) and expr[i + 1].isdigit()):
            j = i + 1
            while j < len(expr) and (expr[j].isdigit() or expr[j] == "."):
                j += 1
            tokens.append(("num", expr[i:j]))
            i = j
            continue

        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < len(expr) and (expr[j].isalnum() or expr[j] in "_.:"):
                j += 1
            tokens.append(("name", expr[i:j]))
            i = j
            continue

        return None

    return tokens


def as_vector(value, size: int):
    if isinstance(value, list):
        if len(value) == size:
            return value
        if len(value) > size:
            return value[:size]
        if not value:
            return [0.0] * size
        expanded = list(value)
        while len(expanded) < size:
            expanded.append(expanded[-1])
        return expanded
    return [value] * size


def apply_binary_op(op_type, left, right):
    left_is_vec = isinstance(left, list)
    right_is_vec = isinstance(right, list)

    if not left_is_vec and not right_is_vec:
        if op_type is ast.Div and right == 0:
            return 0.0
        return {
            ast.Add: left + right,
            ast.Sub: left - right,
            ast.Mult: left * right,
            ast.Div: 0.0 if right == 0 else left / right,
        }.get(op_type)

    size = len(left) if left_is_vec else len(right)
    lv = as_vector(left, size)
    rv = as_vector(right, size)
    out = []
    for a, b in zip(lv, rv):
        if op_type is ast.Add:
            out.append(a + b)
        elif op_type is ast.Sub:
            out.append(a - b)
        elif op_type is ast.Mult:
            out.append(a * b)
        elif op_type is ast.Div:
            out.append(0.0 if b == 0 else a / b)
    return out


def eval_ast(node, env: dict[str, float | list[float]]):
    if isinstance(node, ast.Expression):
        return eval_ast(node.body, env)

    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = eval_ast(node.operand, env)
        if value is None:
            return None
        if isinstance(value, list):
            if isinstance(node.op, ast.USub):
                return [-x for x in value]
            return value
        return -value if isinstance(node.op, ast.USub) else value

    if isinstance(node, ast.Name):
        return env.get(node.id)

    if isinstance(node, ast.BinOp) and type(node.op) in {ast.Add, ast.Sub, ast.Mult, ast.Div}:
        left = eval_ast(node.left, env)
        right = eval_ast(node.right, env)
        if left is None or right is None:
            return None
        return apply_binary_op(type(node.op), left, right)

    return None


def evaluate_expression(expr: str, var_values: dict[str, list[float]], stat_values: dict[str, float]):
    if expr is None:
        return None

    raw = expr.strip()
    if not raw:
        return None

    raw = raw.replace("%", "")
    tokens = tokenize_expression(raw)
    if not tokens:
        return None

    safe_parts = []
    env: dict[str, float | list[float]] = {}
    alias = {}
    alias_idx = 0

    for ttype, text in tokens:
        if ttype == "op":
            safe_parts.append(text)
            continue
        if ttype == "num":
            safe_parts.append(text)
            continue

        value = None
        if text in var_values:
            value = var_values[text]
        elif text in stat_values:
            value = stat_values[text]
        elif text.lower() in stat_values:
            value = stat_values[text.lower()]

        if value is None:
            return None

        if text not in alias:
            name = f"v{alias_idx}"
            alias_idx += 1
            alias[text] = name
            env[name] = value
        safe_parts.append(alias[text])

    safe_expr = "".join(safe_parts)
    try:
        tree = ast.parse(safe_expr, mode="eval")
    except SyntaxError:
        return None

    return eval_ast(tree, env)


def format_number(value: float) -> str:
    if abs(value) < 1e-9:
        value = 0.0
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def format_value_for_desc(value):
    if isinstance(value, list):
        formatted = [format_number(v) for v in value]
        if len(set(formatted)) == 1:
            return formatted[0]
        return f"[{' / '.join(formatted)}]"
    return format_number(value)


def replace_tokens_with_values(desc: str, token_to_value_text: dict[str, str], unresolved_mode: str = "marker") -> str:
    def _replace(match: re.Match) -> str:
        token = match.group(1)
        text = token_to_value_text.get(token)
        if text is not None:
            return text
        if unresolved_mode == "keep":
            return match.group(0)
        return f"{{UNRESOLVED:{token}}}"

    return TOKEN_RE.sub(_replace, desc or "")


def normalize_name_set(names: list[str]) -> dict[str, list[str]]:
    table: dict[str, list[str]] = {}
    for name in names:
        table.setdefault(normalize(name), []).append(name)
    return table


def detect_category(token: str) -> str:
    t = token.lower()
    if "damage" in t:
        return "damage"
    if "heal" in t:
        return "heal"
    if "shield" in t:
        return "shield"
    if "attackspeed" in t or t.endswith("as"):
        return "attack_speed"
    if "duration" in t:
        return "duration"
    if "range" in t or "radius" in t or "distance" in t:
        return "range"
    if t.startswith("num"):
        return "count"
    return "other"


def variable_to_term(var_name: str, stats_keys: set[str]) -> str:
    lower = var_name.lower()

    if "percent" in lower and "health" in lower and "hp" in stats_keys:
        return f"{var_name}*hp"
    if "percent" in lower and "armor" in lower and "armor" in stats_keys:
        return f"{var_name}*armor"
    if ("mr" in lower or "magicresist" in lower) and "ratio" in lower and "magicresist" in stats_keys:
        return f"{var_name}*magicResist"

    return var_name


def score_candidate(token: str, candidate: str) -> float:
    token_n = normalize(token)
    cand_n = normalize(candidate)
    if not token_n or not cand_n:
        return 0.0

    ratio = SequenceMatcher(None, token_n, cand_n).ratio()
    bonus = 0.0
    if cand_n in token_n or token_n in cand_n:
        bonus += 0.15
    return min(1.0, ratio + bonus)


def ranked_candidates(token: str, variables: list[str], limit: int = 5) -> list[str]:
    ranked = sorted(variables, key=lambda v: score_candidate(token, v), reverse=True)
    return ranked[:limit]


def resolve_direct(token: str, variables: list[str], norm_map: dict[str, list[str]]):
    if token in variables:
        return token, "exact", "high"

    m = FORMULA_SUFFIX_RE.fullmatch(token)
    if m and m.group(1) in variables:
        return m.group(1), "strip_formula_suffix", "high"

    for prefix in SIMPLE_PREFIXES:
        if token.startswith(prefix):
            base = token[len(prefix) :]
            if base in variables:
                return base, "drop_prefix", "high"

    for suffix in SIMPLE_SUFFIXES:
        if token.endswith(suffix):
            base = token[: -len(suffix)]
            if base in variables:
                return base, "drop_suffix", "high"

    n = normalize(token)
    matches = norm_map.get(n, [])
    if len(matches) == 1:
        return matches[0], "normalized", "medium"

    if "_" in token:
        parts = token.split("_")
        for part in parts:
            if part in variables:
                return part, "underscore_part", "medium"

        tail = parts[-1]
        damage_variant = f"{tail}Damage"
        if damage_variant in variables:
            return damage_variant, "suffix_damage", "medium"

    return None, None, None


def resolve_semantic(token: str, variables: list[str], stats_keys: set[str]):
    category = detect_category(token)
    token_lower = token.lower()

    if token.startswith("Total") and category == "damage":
        if "ADDamage" in variables and "APDamage" in variables:
            return "ADDamage + APDamage", "total_ap_ad", "medium"

    if token.startswith("Total") and category == "heal":
        if "APHealing" in variables:
            for v in variables:
                lv = v.lower()
                if "percent" in lv and "health" in lv and "heal" in lv:
                    return f"{v}*hp + APHealing", "total_percent_health_heal", "medium"

    if category in {"damage", "heal", "shield"}:
        relevant = []
        for v in variables:
            lv = v.lower()
            if category in lv:
                relevant.append(v)
                continue
            if category == "damage" and ("dps" in lv or "ratio" in lv and "damage" in lv):
                relevant.append(v)
            if category == "heal" and "restore" in lv:
                relevant.append(v)

        if "secondary" in token_lower:
            secondary = [v for v in relevant if "secondary" in v.lower() or "explosion" in v.lower()]
            if len(secondary) == 1:
                return variable_to_term(secondary[0], stats_keys), "semantic_secondary", "medium"
            if len(secondary) > 1:
                expr = " + ".join(variable_to_term(v, stats_keys) for v in secondary)
                return expr, "semantic_secondary_sum", "low"

        if "bonus" in token_lower:
            bonus = [v for v in relevant if "bonus" in v.lower()]
            if len(bonus) == 1:
                return variable_to_term(bonus[0], stats_keys), "semantic_bonus", "medium"

        if len(relevant) == 1:
            return variable_to_term(relevant[0], stats_keys), "semantic_single", "medium"
        if 1 < len(relevant) <= 3:
            expr = " + ".join(variable_to_term(v, stats_keys) for v in relevant)
            return expr, "semantic_sum", "low"

    if category == "attack_speed":
        hits = [v for v in variables if "attackspeed" in v.lower() or v.lower().endswith("as")]
        if len(hits) == 1:
            return hits[0], "semantic_attack_speed", "medium"
        if len(hits) > 1:
            preferred = sorted(hits, key=lambda v: ("base" not in v.lower(), len(v)))
            return preferred[0], "semantic_attack_speed_pick", "low"

    if category == "range":
        hits = [v for v in variables if any(k in v.lower() for k in ("range", "radius", "distance"))]
        if len(hits) == 1:
            return hits[0], "semantic_range", "medium"

    if category == "duration":
        hits = [v for v in variables if "duration" in v.lower()]
        if len(hits) == 1:
            return hits[0], "semantic_duration", "medium"

    if category == "count":
        hits = [v for v in variables if v.lower().startswith("num") or "count" in v.lower()]
        if len(hits) == 1:
            return hits[0], "semantic_count", "medium"

    return None, None, None


def build_mapping(
    champions: list[dict],
    overrides: dict[tuple[str, str], str] | None = None,
):
    overrides = overrides or {}

    mappings: list[dict] = []
    unresolved: list[dict] = []
    diagnostics: list[dict] = []

    for champ in champions:
        api_name = champ.get("apiName", "")
        ability = champ.get("ability") or {}
        desc = ability.get("descRaw") or ability.get("desc") or ""
        variables = [v.get("name") for v in (ability.get("variables") or []) if isinstance(v, dict) and v.get("name")]
        stats = champ.get("stats") or {}
        stats_keys = {k.lower() for k in stats.keys()}
        norm_map = normalize_name_set(variables)

        for token in extract_tokens(desc):
            key = (api_name, token)
            if key in overrides:
                variable = overrides[key]
                mappings.append({"apiName": api_name, "token": token, "variable": variable})
                diagnostics.append(
                    {
                        "apiName": api_name,
                        "token": token,
                        "variable": variable,
                        "source": "override",
                        "confidence": "high",
                    }
                )
                continue

            variable, source, confidence = resolve_direct(token, variables, norm_map)
            if variable is not None:
                mappings.append({"apiName": api_name, "token": token, "variable": variable})
                diagnostics.append(
                    {
                        "apiName": api_name,
                        "token": token,
                        "variable": variable,
                        "source": source,
                        "confidence": confidence,
                    }
                )
                continue

            variable, source, confidence = resolve_semantic(token, variables, stats_keys)
            if variable is not None:
                mappings.append({"apiName": api_name, "token": token, "variable": variable})
                diagnostics.append(
                    {
                        "apiName": api_name,
                        "token": token,
                        "variable": variable,
                        "source": source,
                        "confidence": confidence,
                    }
                )
                continue

            unresolved.append(
                {
                    "apiName": api_name,
                    "token": token,
                    "candidates": ranked_candidates(token, variables),
                    "variables": variables,
                }
            )
            diagnostics.append(
                {
                    "apiName": api_name,
                    "token": token,
                    "variable": None,
                    "source": "unresolved",
                    "confidence": "none",
                }
            )

    mappings.sort(key=lambda x: (x["apiName"], x["token"]))
    diagnostics.sort(key=lambda x: (x["apiName"], x["token"]))
    unresolved.sort(key=lambda x: (x["apiName"], x["token"]))
    return mappings, unresolved, diagnostics


def build_champions_with_resolved_desc(
    champions: list[dict],
    mappings: list[dict],
    star_indexes: tuple[int, ...],
    replace_desc: bool,
) -> list[dict]:
    mapping_by_key = {(m["apiName"], m["token"]): m["variable"] for m in mappings}
    updated_champions: list[dict] = []

    for champ in champions:
        api_name = champ.get("apiName", "")
        ability = champ.get("ability") or {}
        desc_template = ability.get("descRaw") or ability.get("desc") or ""
        tokens = extract_tokens(desc_template)

        token_to_expr = {token: mapping_by_key.get((api_name, token)) for token in tokens}
        resolved_desc = replace_tokens_in_desc(desc_template, token_to_expr)

        unresolved_tokens = [token for token in tokens if token_to_expr.get(token) is None]
        var_values, stat_values = build_value_context(champ, star_indexes)

        token_to_value_text: dict[str, str] = {}
        eval_unresolved_tokens = []
        for token in tokens:
            expr = token_to_expr.get(token)
            if expr is None:
                continue
            evaluated = evaluate_expression(expr, var_values, stat_values)
            if evaluated is None:
                eval_unresolved_tokens.append(token)
                continue
            token_to_value_text[token] = format_value_for_desc(evaluated)

        value_desc = replace_tokens_with_values(desc_template, token_to_value_text, unresolved_mode="keep")

        champ_copy = dict(champ)
        ability_copy = insert_desc_resolved_field(dict(ability), resolved_desc)
        ability_copy["descValues"] = value_desc
        ability_copy["unresolvedTokens"] = unresolved_tokens
        ability_copy["unresolvedValueTokens"] = eval_unresolved_tokens
        if replace_desc:
            ability_copy["descRaw"] = desc_template
            ability_copy["desc"] = value_desc
        champ_copy["ability"] = ability_copy
        updated_champions.append(champ_copy)

    return updated_champions


def load_overrides(path: Path | None) -> dict[tuple[str, str], str]:
    if path is None or not path.exists():
        return {}

    raw = load_json(path)
    result: dict[tuple[str, str], str] = {}
    if isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict):
                continue
            api_name = row.get("apiName")
            token = row.get("token")
            variable = row.get("variable")
            if api_name and token and variable is not None:
                result[(api_name, token)] = variable
    return result


def write_json(path: Path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def summarize(diagnostics: list[dict]) -> dict:
    total = len(diagnostics)
    unresolved = sum(1 for d in diagnostics if d["source"] == "unresolved")
    resolved = total - unresolved

    by_source: dict[str, int] = {}
    for row in diagnostics:
        by_source[row["source"]] = by_source.get(row["source"], 0) + 1

    by_confidence: dict[str, int] = {}
    for row in diagnostics:
        by_confidence[row["confidence"]] = by_confidence.get(row["confidence"], 0) + 1

    return {
        "totalTokens": total,
        "resolvedTokens": resolved,
        "unresolvedTokens": unresolved,
        "resolvedRate": round((resolved / total) * 100, 2) if total else 0.0,
        "bySource": dict(sorted(by_source.items(), key=lambda x: x[0])),
        "byConfidence": dict(sorted(by_confidence.items(), key=lambda x: x[0])),
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate token->variable mapping from TFT champion ability descriptions."
    )
    parser.add_argument("--champions", default="set16_champions_full.json", help="Champion JSON input path.")
    parser.add_argument("--out-map", default="tft16_auto_map.json", help="Resolved mapping output path.")
    parser.add_argument("--out-unresolved", default="tft16_unresolved.json", help="Unresolved token output path.")
    parser.add_argument("--out-report", default="tft16_auto_report.json", help="Diagnostic report output path.")
    parser.add_argument(
        "--overrides",
        default="tft16.json",
        help="Optional manual mapping file (same schema as tft16.json). If present, values are used first.",
    )
    parser.add_argument(
        "--no-overrides",
        action="store_true",
        help="Disable overrides even if --overrides file exists.",
    )
    parser.add_argument(
        "--write-resolved-desc",
        action="store_true",
        help="Write ability.descResolved/descValues/unresolvedTokens into champion JSON.",
    )
    parser.add_argument(
        "--out-champions",
        default=None,
        help="Output path for champion JSON with descResolved. Default: overwrite --champions.",
    )
    parser.add_argument(
        "--replace-desc",
        action="store_true",
        help="When writing champion JSON, overwrite ability.desc with rendered numeric desc and keep original in descRaw.",
    )
    parser.add_argument(
        "--star-indexes",
        default="1,2,3",
        help="Comma-separated indexes from variable value arrays used for rendering, e.g. 1,2,3.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    champions_path = Path(args.champions)
    out_map_path = Path(args.out_map)
    out_unresolved_path = Path(args.out_unresolved)
    out_report_path = Path(args.out_report)
    overrides_path = None if args.no_overrides else (Path(args.overrides) if args.overrides else None)
    star_indexes = parse_star_indexes(args.star_indexes)

    champions = load_json(champions_path)
    overrides = load_overrides(overrides_path)

    mappings, unresolved, diagnostics = build_mapping(champions, overrides)
    summary = summarize(diagnostics)

    write_json(out_map_path, mappings)
    write_json(out_unresolved_path, {"count": len(unresolved), "entries": unresolved})
    write_json(out_report_path, {"summary": summary, "diagnostics": diagnostics})

    if args.write_resolved_desc:
        updated_champions = build_champions_with_resolved_desc(
            champions,
            mappings,
            star_indexes=star_indexes,
            replace_desc=args.replace_desc,
        )
        out_champions_path = Path(args.out_champions) if args.out_champions else champions_path
        write_json(out_champions_path, updated_champions)

    print(f"champions: {len(champions)}")
    print(f"tokens: {summary['totalTokens']}")
    print(f"resolved: {summary['resolvedTokens']}")
    print(f"unresolved: {summary['unresolvedTokens']}")
    print(f"resolvedRate: {summary['resolvedRate']}%")
    print(f"overridesLoaded: {len(overrides)}")
    print(f"outMap: {out_map_path}")
    print(f"outUnresolved: {out_unresolved_path}")
    print(f"outReport: {out_report_path}")
    print(f"starIndexes: {','.join(str(x) for x in star_indexes)}")
    if args.write_resolved_desc:
        print(f"outChampions: {out_champions_path}")


if __name__ == "__main__":
    main()
