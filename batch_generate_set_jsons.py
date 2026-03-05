import argparse
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_SETS = (16, 15, 14, 13, 12, 11, 10)


def parse_sets(raw: str) -> list[int]:
    values = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        values.append(int(part))
    if not values:
        return list(DEFAULT_SETS)
    return values


def run_cmd(cmd: list[str], cwd: Path):
    printable = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    print(f"$ {printable}")
    subprocess.run(cmd, cwd=str(cwd), check=True)


def maybe_copy_override(root_dir: Path, set_dir: Path, set_number: int) -> Path:
    set_override_path = set_dir / f"tft{set_number}.json"
    if set_override_path.exists():
        return set_override_path

    root_override_path = root_dir / f"tft{set_number}.json"
    if root_override_path.exists():
        shutil.copy2(root_override_path, set_override_path)
        print(f"copied override: {root_override_path} -> {set_override_path}")

    return set_override_path


def generate_for_set(
    root_dir: Path,
    set_number: int,
    out_root: Path,
    extract_script: Path,
    mapping_script: Path,
    locale: str,
    version: str,
    auto_version: bool,
    all_units: bool,
):
    set_dir = out_root / f"set{set_number}"
    set_dir.mkdir(parents=True, exist_ok=True)

    champions_path = set_dir / f"set{set_number}_champions_full.json"
    map_path = set_dir / f"tft{set_number}_auto_map.json"
    unresolved_path = set_dir / f"tft{set_number}_unresolved.json"
    report_path = set_dir / f"tft{set_number}_auto_report.json"
    map_no_override_path = set_dir / f"tft{set_number}_auto_map_no_override.json"
    unresolved_no_override_path = set_dir / f"tft{set_number}_unresolved_no_override.json"
    report_no_override_path = set_dir / f"tft{set_number}_auto_report_no_override.json"

    override_path = maybe_copy_override(root_dir, set_dir, set_number)

    extract_cmd = [
        sys.executable,
        str(extract_script),
        "--set",
        str(set_number),
        "--locale",
        locale,
        "--version",
        version,
        "--output",
        str(champions_path),
    ]
    if not auto_version:
        extract_cmd.append("--no-auto-version")
    if all_units:
        extract_cmd.append("--all-units")

    run_cmd(extract_cmd, root_dir)

    map_cmd = [
        sys.executable,
        str(mapping_script),
        "--champions",
        str(champions_path),
        "--out-map",
        str(map_path),
        "--out-unresolved",
        str(unresolved_path),
        "--out-report",
        str(report_path),
        "--overrides",
        str(override_path),
    ]
    run_cmd(map_cmd, root_dir)

    map_no_override_cmd = [
        sys.executable,
        str(mapping_script),
        "--champions",
        str(champions_path),
        "--out-map",
        str(map_no_override_path),
        "--out-unresolved",
        str(unresolved_no_override_path),
        "--out-report",
        str(report_no_override_path),
        "--no-overrides",
    ]
    run_cmd(map_no_override_cmd, root_dir)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate TFT champions/mapping/unresolved/report JSON files by set folder."
    )
    parser.add_argument(
        "--sets",
        default=",".join(str(v) for v in DEFAULT_SETS),
        help="Comma-separated set numbers, e.g. 16,15,14,13,12,11,10",
    )
    parser.add_argument(
        "--out-root",
        default="seasons",
        help="Output root folder. Set folders will be created inside this path.",
    )
    parser.add_argument("--locale", default="ko_kr", help="CommunityDragon locale, default: ko_kr.")
    parser.add_argument("--version", default="latest", help="Preferred data version, default: latest.")
    parser.add_argument(
        "--no-auto-version",
        action="store_true",
        help="Disable fallback search over patch versions for missing sets.",
    )
    parser.add_argument(
        "--all-units",
        action="store_true",
        help="Include non-playable units (default keeps only cost 1-5 units).",
    )
    parser.add_argument(
        "--extract-script",
        default="extract_set16_champions.py",
        help="Path to extraction script.",
    )
    parser.add_argument(
        "--mapping-script",
        default="generate_desc_mapping.py",
        help="Path to token mapping script.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    root_dir = Path.cwd()
    out_root = (root_dir / args.out_root).resolve()
    extract_script = (root_dir / args.extract_script).resolve()
    mapping_script = (root_dir / args.mapping_script).resolve()

    if not extract_script.exists():
        raise FileNotFoundError(f"extract script not found: {extract_script}")
    if not mapping_script.exists():
        raise FileNotFoundError(f"mapping script not found: {mapping_script}")

    out_root.mkdir(parents=True, exist_ok=True)
    sets = parse_sets(args.sets)
    print(f"sets: {sets}")
    print(f"outRoot: {out_root}")

    for set_number in sets:
        print(f"=== set {set_number} ===")
        generate_for_set(
            root_dir=root_dir,
            set_number=set_number,
            out_root=out_root,
            extract_script=extract_script,
            mapping_script=mapping_script,
            locale=args.locale,
            version=args.version,
            auto_version=not args.no_auto_version,
            all_units=args.all_units,
        )

    print("done")


if __name__ == "__main__":
    main()
