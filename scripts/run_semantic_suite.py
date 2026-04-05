"""运行语义回归检查并输出 JSON 报告。"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict

SEMANTIC_CASES = {
    "priority": {
        "path": "tests/e2e/test_semantics_regression.py",
        "expr": "priority_conflict_semantic",
    },
    "closed_bar": {
        "path": "tests/e2e/test_semantics_regression.py",
        "expr": "closed_bar_dedupe_semantic",
    },
    "daily_lock": {
        "path": "tests/e2e/test_semantics_regression.py",
        "expr": "daily_lock_semantic",
    },
    "protection": {
        "path": "tests/e2e/test_semantics_regression.py",
        "expr": "protection_stage_semantic",
    },
    "persistence": {
        "path": "tests/e2e/test_semantics_regression.py",
        "expr": "restart_recovery_semantic",
    },
    "tick_same_bar": {
        "path": "tests/e2e/test_semantics_regression.py",
        "expr": "tick_same_bar_dedupe_semantic",
    },
    "tick_reconnect": {
        "path": "tests/e2e/test_semantics_regression.py",
        "expr": "tick_reconnect_idempotence_semantic",
    },
    "tick_replay_parity": {
        "path": "tests/integration/test_tick_replay_parity.py",
        "expr": "legacy_vs_ingress",
    },
    "tick_protection": {
        "path": "tests/integration/test_tick_burst_protection.py",
        "expr": "same_bar_burst_skips_no_change_modify or protection_change_emits_single_modify",
    },
}


def _run_case(case_name: str, path: str, test_expr: str) -> Dict[str, object]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        path,
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

    results = [
        _run_case(case_name, case["path"], case["expr"])
        for case_name, case in SEMANTIC_CASES.items()
    ]
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
