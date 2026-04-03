"""Optional MT5 demo smoke test (disabled unless RUN_MT5_SMOKE=1)."""

import importlib
import os

import pytest


@pytest.mark.skipif(os.getenv("RUN_MT5_SMOKE") != "1", reason="RUN_MT5_SMOKE is not enabled")
def test_mt5_demo_smoke() -> None:
    try:
        mt5 = importlib.import_module("MetaTrader5")
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"MT5_DEMO_ENV_MISSING: import failed ({exc})")

    if not mt5.initialize():
        pytest.fail("MT5_DEMO_ENV_MISSING: mt5.initialize() returned False")

    mt5.shutdown()
