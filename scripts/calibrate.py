#!/usr/bin/env python3
"""Fit offline temperatures from labeled calibration data and saved raw predictions."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openjev.calibration import fit_calibration, load_dataset, load_response_records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="JSONL with split=calibration")
    parser.add_argument("--responses", required=True, help="Raw response artifact written by scripts/evaluate.py")
    parser.add_argument("--out", default="artifacts/calibration.json")
    parser.add_argument("--min-samples", type=int, default=20, help="Minimum labeled questions per type (default: 20; not a statistical sufficiency guarantee)")
    args = parser.parse_args(argv)
    try:
        items = load_dataset(args.data)
        records = load_response_records(args.responses, items)
        failed = [item["id"] for item in items if records[item["id"]].get("error") or not isinstance(records[item["id"]].get("response"), dict)]
        if failed:
            raise ValueError("Calibration response file contains failed/missing predictions: " + ", ".join(failed) + ". Resolve failures or make an explicit, documented dataset revision; nothing is silently dropped.")
        artifact = fit_calibration([(item, records[item["id"]]["response"]) for item in items], source=args.data, min_samples=args.min_samples)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps({"out": str(out), "model": artifact["model"], "coverage": artifact["coverage"], "skipped_labels": artifact["skipped_labels"], "note": artifact["note"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
