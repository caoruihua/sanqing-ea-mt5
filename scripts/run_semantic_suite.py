"""Run semantic regression checks and emit JSON report."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict

SEMANTIC_CASES = {
    "priority": "priority_conflict_semantic",
    "closed_bar": "closed_bar_dedupe_semantic",
    "daily_lock": "daily_lock_semantic",
    "protection": "protection_stage_semantic",
    "persistence": "restart_recovery_semantic",
}


def _run_case(case_name: str, test_expr: str) -> Dict[str, object]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/e2e/test_semantics_regression.py",
        "-k",
        test_expr,
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return {
        "case": case_name,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run semantic regression suite")
    parser.add_argument("--out", required=True, help="Path to JSON output report")
    args = parser.parse_args()

    results = [_run_case(case_name, expr) for case_name, expr in SEMANTIC_CASES.items()]
    all_pass = all(result["status"] == "PASS" for result in results)
    report = {
        "suite": "semantic-regression",
        "overall": "PASS" if all_pass else "FAIL",
        "results": results,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
