"""Unit tests for MT5 retcode normalization."""

import pytest

from src.adapters.mt5_broker import UnknownRetcodeError, normalize_retcode


def test_known_success_retcode_maps_to_success() -> None:
    mapped = normalize_retcode(10009)

    assert mapped.success is True
    assert mapped.retryable is False
    assert mapped.reason == "DONE"


def test_known_retryable_retcode_maps_to_retryable_error() -> None:
    mapped = normalize_retcode(10004)

    assert mapped.success is False
    assert mapped.retryable is True
    assert mapped.reason == "REQUOTE"


def test_unknown_retcode_raises_unknown_retcode_error() -> None:
    with pytest.raises(UnknownRetcodeError, match="Unknown MT5 retcode: 19999"):
        normalize_retcode(19999)
