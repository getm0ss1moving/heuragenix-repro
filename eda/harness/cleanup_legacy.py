"""Move pre-audit metric artifacts into results/legacy_wrong_metrics/.

These files were produced before the 2026-09-22 metric audit (wrong WNS field,
power unit bug, DRC double count, old HPWL parser).  They are kept for
provenance but must not be used for reports, training, or selectors.

Run from eda/:
  python3 harness/cleanup_legacy.py --dry-run
  python3 harness/cleanup_legacy.py --apply
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

OLD_PREFIXES = (
    "phase0_sweep_",
    "phase0_stats_",
    "PHASE0_STATS_",
    "phase0_selector_",
    "PHASE0_SELECTOR_",
    "selector_dataset_",
    "selector_sft_",
    "selector_preferences_",
    "phase0_report_",
)

OLD_CANDIDATE_SUBSTR = ("_candidates",)

EXCLUDE_SUBSTR = ("wnsfix", "canonical", "legacy_wrong_metrics", "PHASE0_REPORT_0006",
                  "PHASE0_REPORT_0003", "PHASE0_REPORT_0004", "PHASE0_REPORT_0005")


def should_move(path: Path):
    name = path.name
    if path.is_dir():
        return False
    if any(x in name for x in EXCLUDE_SUBSTR):
        return False
    if any(name.startswith(p) for p in OLD_PREFIXES):
        return True
    if any(s in name for s in OLD_CANDIDATE_SUBSTR):
        return True
    if name.startswith("gcd_") and name.endswith("_metrics.json"):
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Move obsolete pre-audit metric artifacts to results/legacy_wrong_metrics")
    parser.add_argument("--results-dir", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    results_dir = Path(args.results_dir) if args.results_dir else Path(__file__).resolve().parent.parent / "results"
    dest_dir = results_dir / "legacy_wrong_metrics"
    files = sorted([p for p in results_dir.iterdir() if should_move(p)])
    print("results_dir", results_dir)
    print("planned_moves", len(files))
    for p in files:
        print(" ", p.name)
    if not args.apply:
        print("dry_run: pass --apply to move")
        return
    dest_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for p in files:
        dest = dest_dir / p.name
        if dest.exists():
            dest = dest_dir / (p.stem + "__dup" + p.suffix)
        shutil.move(str(p), str(dest))
        manifest.append(p.name + " -> " + dest.name)
    readme = dest_dir / "README.md"
    readme.write_text(
        "# legacy_wrong_metrics\n\n"
        "这些文件产生于 2026-09-22 指标口径审计之前，包含错误的口径：\n"
        "- WNS 字段把 `DRT::worst_slack_min`（hold）当成 WNS；\n"
        "- OpenLane power 单位曾按 µW 误换算；\n"
        "- DRC 曾把 detailed-route 总数与子计数、Magic/KLayout 混加；\n"
        "- HPWL 解析曾漏 `( PIN port )`/换行 pin。\n\n"
        "**禁止用于报告、训练、selector 或论文。** 新口径与重算产物见 "
        "`../canonical/`、`../PHASE0_REPORT_0006_WNS_FIX.md`、`docs/METRIC_CONVENTIONS.md`。\n"
    )
    (dest_dir / "MANIFEST.txt").write_text("\n".join(sorted(manifest)) + "\n")
    print("moved", len(manifest), "files to", dest_dir)
    print("manifest", dest_dir / "MANIFEST.txt")


if __name__ == "__main__":
    main()
