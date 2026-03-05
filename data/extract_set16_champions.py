import argparse
import json
import re
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE_URL = "https://raw.communitydragon.org"
VERSIONS_INDEX_URL = f"{BASE_URL}/json/"
DEFAULT_SET_NUMBER = 16
DEFAULT_LOCALE = "ko_kr"


def load_data(url: str) -> dict | list:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=30) as resp:
        return json.load(resp)


def find_set_entry(data: dict, set_number: int) -> dict | None:
    set_data = data.get("setData", [])
    target_number = str(set_number)
    preferred_mutator = f"TFTSet{set_number}"

    for entry in set_data:
        if str(entry.get("number")) == target_number and entry.get("mutator") == preferred_mutator:
            return entry

    for entry in set_data:
        if str(entry.get("number")) == target_number:
            return entry

    return None


def extract_champions(set_entry: dict, set_number: int, only_playable_units: bool = True) -> list[dict]:
    champions = []
    seen_api_names = set()

    for champ in set_entry.get("champions", []):
        api_name = champ.get("apiName", "")
        cost = champ.get("cost")

        if not api_name.startswith(f"TFT{set_number}_"):
            continue

        if only_playable_units and cost not in {1, 2, 3, 4, 5}:
            continue

        if not api_name or api_name in seen_api_names:
            continue

        seen_api_names.add(api_name)
        champions.append(champ)

    champions.sort(key=lambda x: (x.get("cost", 999), x.get("name", "")))
    return champions


def is_patch_version(name: str) -> bool:
    return bool(re.fullmatch(r"\d+\.\d+", name or ""))


def fetch_patch_versions() -> list[str]:
    payload = load_data(VERSIONS_INDEX_URL)
    versions = []
    if isinstance(payload, list):
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name", "")
            if not is_patch_version(name):
                continue
            major, minor = (int(part) for part in name.split("."))
            versions.append((major, minor, name))

    versions.sort(reverse=True)
    return [name for _, _, name in versions]


def build_tft_data_url(version: str, locale: str) -> str:
    return f"{BASE_URL}/{quote(version)}/cdragon/tft/{quote(locale)}.json"


def try_load_set_from_version(version: str, locale: str, set_number: int) -> tuple[dict, dict] | None:
    url = build_tft_data_url(version, locale)
    try:
        data = load_data(url)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    set_entry = find_set_entry(data, set_number)
    if set_entry is None:
        return None
    return data, set_entry


def resolve_set_data(
    set_number: int,
    locale: str,
    preferred_version: str,
    auto_version: bool,
) -> tuple[str, dict]:
    primary = try_load_set_from_version(preferred_version, locale, set_number)
    if primary is not None:
        _, set_entry = primary
        return preferred_version, set_entry

    if not auto_version:
        raise ValueError(
            f"Could not find set {set_number} in version '{preferred_version}' and auto version discovery is disabled."
        )

    for version in fetch_patch_versions():
        if version == preferred_version:
            continue
        found = try_load_set_from_version(version, locale, set_number)
        if found is None:
            continue
        _, set_entry = found
        return version, set_entry

    raise ValueError(f"Could not find set {set_number} in CommunityDragon TFT data.")


def parse_args():
    parser = argparse.ArgumentParser(description="Extract TFT set champions from CommunityDragon.")
    parser.add_argument("--set", type=int, default=DEFAULT_SET_NUMBER, help="TFT set number, e.g. 16.")
    parser.add_argument("--locale", default=DEFAULT_LOCALE, help="Locale code, e.g. ko_kr.")
    parser.add_argument("--version", default="latest", help="Preferred CommunityDragon version, default: latest.")
    parser.add_argument(
        "--no-auto-version",
        action="store_true",
        help="Disable fallback search through patch versions when the preferred version does not include the target set.",
    )
    parser.add_argument(
        "--all-units",
        action="store_true",
        help="Include non-playable units too (default keeps only cost 1-5 units).",
    )
    parser.add_argument("--output", default=None, help="Output JSON path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    set_number = args.set
    output_path = Path(args.output) if args.output else Path(f"set{set_number}_champions_full.json")

    source_version, set_entry = resolve_set_data(
        set_number=set_number,
        locale=args.locale,
        preferred_version=args.version,
        auto_version=not args.no_auto_version,
    )
    champions = extract_champions(
        set_entry,
        set_number,
        only_playable_units=not args.all_units,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(champions, f, ensure_ascii=False, indent=2)

    print(f"sourceVersion: {source_version}")
    print(f"set: {set_number}")
    print(f"locale: {args.locale}")
    print(f"onlyPlayableUnits: {not args.all_units}")
    print(f"saved: {len(champions)}")
    print(f"output: {output_path}")


if __name__ == "__main__":
    main()
