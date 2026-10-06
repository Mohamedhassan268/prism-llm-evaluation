"""Refresh verified local reports while resumable jobs continue; never execute code."""

import argparse
import subprocess
import sys
import time
from pathlib import Path

from prismqa.records import read_json, write_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    while True:
        result = subprocess.run(
            [sys.executable, "scripts/summarize_calibration.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode:
            write_json(
                ROOT / "reports/calibration-monitor.json",
                {"status": "report_error", "diagnostic": result.stderr[-4096:]},
            )
            return 1
        checkpoint = read_json(ROOT / "reports/calibration-checkpoint.json")
        complete = all(
            checkpoint[stage]["status"] == "complete" for stage in ("baseline", "extended")
        )
        states = list((ROOT / "runs").glob("calibration-batch-*/state.json"))
        records = list((ROOT / "runs").glob("calibration-batch-*/records/*.json"))
        latest = max((p.stat().st_mtime for p in states + records), default=time.time())
        stalled = time.time() - latest > 1200
        write_json(
            ROOT / "reports/calibration-monitor.json",
            {
                "status": "complete" if complete else "stalled" if stalled else "running",
                "completed_baseline_models": len(checkpoint["baseline"]["completed_models"]),
                "completed_extended_models": len(checkpoint["extended"]["completed_models"]),
                "updated_unix_seconds": time.time(),
                "note": "Verified completed batches only; "
                "this monitor does not imply active-job success",
            },
        )
        if args.once or complete or stalled:
            return 0
        time.sleep(30)


if __name__ == "__main__":
    raise SystemExit(main())
