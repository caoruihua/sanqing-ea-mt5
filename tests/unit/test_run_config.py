"""Unit tests for app.run configuration helpers."""

import importlib

import pytest

_run = importlib.import_module("src.app.run")


def test_load_config_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        _run._load_config("config/does-not-exist.ini")


def test_resolve_timeframe_unsupported_raises() -> None:
    class _FakeMt5:
        TIMEFRAME_M1 = 1
        TIMEFRAME_M5 = 5
        TIMEFRAME_M15 = 15
        TIMEFRAME_M30 = 30
        TIMEFRAME_H1 = 60
        TIMEFRAME_H4 = 240
        TIMEFRAME_D1 = 1440

    with pytest.raises(ValueError, match="Unsupported timeframe"):
        _run._resolve_timeframe(_FakeMt5, 2)


def test_resolve_timeframe_m5() -> None:
    class _FakeMt5:
        TIMEFRAME_M1 = 1
        TIMEFRAME_M5 = 500
        TIMEFRAME_M15 = 15
        TIMEFRAME_M30 = 30
        TIMEFRAME_H1 = 60
        TIMEFRAME_H4 = 240
        TIMEFRAME_D1 = 1440

    assert _run._resolve_timeframe(_FakeMt5, 5) == 500
