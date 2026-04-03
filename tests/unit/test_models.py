"""
Unit tests for domain models.

Tests specifically for Task 2 domain models serialization/deserialization.
"""

from datetime import datetime

import pytest

from src.domain.models import (
    MarketSnapshot,
    ProtectionStage,
    ProtectionState,
    RuntimeState,
)


class TestRuntimeStateSerialization:
    """Tests for RuntimeState serialization and deserialization."""

    def test_round_trip_serialization_empty(self):
        """Test round-trip serialization with empty state."""
        # Create a basic runtime state
        original = RuntimeState(
            day_key="2026.04.03",
            daily_locked=False,
            daily_closed_profit=0.0,
            trades_today=0,
        )

        # Convert to JSON and back
        json_str = original.to_json()
        reconstructed = RuntimeState.from_json(json_str)

        # Verify all fields match
        assert reconstructed.day_key == original.day_key
        assert reconstructed.daily_locked == original.daily_locked
        assert reconstructed.daily_closed_profit == original.daily_closed_profit
        assert reconstructed.trades_today == original.trades_today
        assert reconstructed.protection_state.protection_stage == ProtectionStage.NONE

    def test_round_trip_serialization_with_protection_state(self):
        """Test round-trip serialization with ProtectionState containing timestamps."""
        # Create protection state with timestamps
        protection = ProtectionState(
            protection_stage=ProtectionStage.STAGE1,
            entry_price=1800.50,
            entry_atr=18.0,
            highest_close_since_entry=1810.50,
            lowest_close_since_entry=1795.50,
            trailing_active=False,
            stage1_activated_at=datetime(2026, 4, 3, 10, 5, 0),
            stage2_activated_at=None,  # Not activated yet
        )

        # Create runtime state with protection state
        original = RuntimeState(
            day_key="2026.04.03",
            daily_locked=False,
            daily_closed_profit=25.0,
            trades_today=5,
            last_entry_bar_time=datetime(2026, 4, 3, 9, 55, 0),
            protection_state=protection,
        )

        # Convert to JSON and back
        json_str = original.to_json()
        reconstructed = RuntimeState.from_json(json_str)

        # Verify top-level fields
        assert reconstructed.day_key == original.day_key
        assert reconstructed.daily_locked == original.daily_locked
        assert reconstructed.daily_closed_profit == original.daily_closed_profit
        assert reconstructed.trades_today == original.trades_today
        assert reconstructed.last_entry_bar_time == original.last_entry_bar_time

        # Verify nested protection state
        assert reconstructed.protection_state is not None
        assert (
            reconstructed.protection_state.protection_stage
            == original.protection_state.protection_stage
        )
        assert reconstructed.protection_state.entry_price == original.protection_state.entry_price
        assert reconstructed.protection_state.entry_atr == original.protection_state.entry_atr
        assert (
            reconstructed.protection_state.highest_close_since_entry
            == original.protection_state.highest_close_since_entry
        )
        assert (
            reconstructed.protection_state.lowest_close_since_entry
            == original.protection_state.lowest_close_since_entry
        )
        assert (
            reconstructed.protection_state.trailing_active
            == original.protection_state.trailing_active
        )

        # Verify timestamps in nested protection state (CRITICAL: the bug fix)
        assert (
            reconstructed.protection_state.stage1_activated_at
            == original.protection_state.stage1_activated_at
        )
        assert (
            reconstructed.protection_state.stage2_activated_at
            == original.protection_state.stage2_activated_at
        )
        assert reconstructed.protection_state.stage2_activated_at is None  # Should be None

    def test_round_trip_serialization_with_stage2_protection(self):
        """Test round-trip serialization with Stage 2 protection and both timestamps."""
        # Create protection state with both timestamps
        protection = ProtectionState(
            protection_stage=ProtectionStage.STAGE2,
            entry_price=1800.50,
            entry_atr=18.0,
            highest_close_since_entry=1820.50,
            lowest_close_since_entry=1790.50,
            trailing_active=True,
            stage1_activated_at=datetime(2026, 4, 3, 10, 5, 0),
            stage2_activated_at=datetime(2026, 4, 3, 10, 15, 0),  # Stage 2 activated
        )

        original = RuntimeState(
            day_key="2026.04.03",
            daily_locked=True,  # Daily locked
            daily_closed_profit=75.0,
            trades_today=12,
            last_entry_bar_time=datetime(2026, 4, 3, 9, 45, 0),
            protection_state=protection,
        )

        # Convert to JSON and back
        json_str = original.to_json()
        reconstructed = RuntimeState.from_json(json_str)

        # Verify all fields
        assert reconstructed.day_key == original.day_key
        assert reconstructed.daily_locked == original.daily_locked
        assert reconstructed.daily_closed_profit == original.daily_closed_profit
        assert reconstructed.trades_today == original.trades_today
        assert reconstructed.last_entry_bar_time == original.last_entry_bar_time

        # Verify nested protection state with timestamps
        assert reconstructed.protection_state.protection_stage == ProtectionStage.STAGE2
        assert (
            reconstructed.protection_state.stage1_activated_at
            == original.protection_state.stage1_activated_at
        )
        assert (
            reconstructed.protection_state.stage2_activated_at
            == original.protection_state.stage2_activated_at
        )
        assert reconstructed.protection_state.stage2_activated_at is not None

    def test_dict_round_trip(self):
        """Test round-trip using dict methods directly."""
        protection = ProtectionState(
            protection_stage=ProtectionStage.STAGE1,
            stage1_activated_at=datetime(2026, 4, 3, 10, 5, 0),
            stage2_activated_at=None,
        )

        original = RuntimeState(
            day_key="2026.04.03",
            protection_state=protection,
        )

        # Convert to dict and back
        data_dict = original.to_dict()
        reconstructed = RuntimeState.from_dict(data_dict)

        # Verify
        assert reconstructed.day_key == original.day_key
        assert (
            reconstructed.protection_state.protection_stage
            == original.protection_state.protection_stage
        )
        assert (
            reconstructed.protection_state.stage1_activated_at
            == original.protection_state.stage1_activated_at
        )
        assert (
            reconstructed.protection_state.stage2_activated_at
            == original.protection_state.stage2_activated_at
        )

    def test_json_structure_with_timestamps(self):
        """Verify JSON structure contains ISO format timestamps."""
        protection = ProtectionState(
            protection_stage=ProtectionStage.STAGE1,
            stage1_activated_at=datetime(2026, 4, 3, 10, 5, 0),
        )

        original = RuntimeState(
            day_key="2026.04.03",
            last_entry_bar_time=datetime(2026, 4, 3, 9, 55, 0),
            protection_state=protection,
        )

        # Convert to dict
        data_dict = original.to_dict()

        # Verify timestamps are strings in ISO format
        assert isinstance(data_dict["last_entry_bar_time"], str)
        assert "2026-04-03T09:55:00" in data_dict["last_entry_bar_time"]

        # Verify nested protection state timestamps
        assert isinstance(data_dict["protection_state"], dict)
        assert isinstance(data_dict["protection_state"]["stage1_activated_at"], str)
        assert "2026-04-03T10:05:00" in data_dict["protection_state"]["stage1_activated_at"]

        # Convert back and verify
        reconstructed = RuntimeState.from_dict(data_dict)
        assert reconstructed.last_entry_bar_time == original.last_entry_bar_time
        assert (
            reconstructed.protection_state.stage1_activated_at
            == original.protection_state.stage1_activated_at
        )

    def test_enum_serialization(self):
        """Verify ProtectionStage enum serializes/deserializes correctly."""
        for stage_enum in [ProtectionStage.NONE, ProtectionStage.STAGE1, ProtectionStage.STAGE2]:
            protection = ProtectionState(protection_stage=stage_enum)
            original = RuntimeState(
                day_key="2026.04.03",
                protection_state=protection,
            )

            # Convert to dict and back
            data_dict = original.to_dict()
            reconstructed = RuntimeState.from_dict(data_dict)

            # Verify enum value preserved
            assert reconstructed.protection_state.protection_stage == stage_enum
            assert data_dict["protection_state"]["protection_stage"] == stage_enum.value


class TestMarketSnapshotValidation:
    """Tests for MarketSnapshot validation."""

    def test_market_snapshot_validation(self):
        """Test MarketSnapshot post-init validation."""
        # Valid snapshot
        snapshot = MarketSnapshot(
            symbol="XAUUSD",
            timeframe=5,
            digits=2,
            magic_number=20260313,
            bid=1800.50,
            ask=1800.55,
            ema_fast=1801.20,
            ema_slow=1799.80,
            atr14=18.0,
            spread_points=5.0,
            last_closed_bar_time=datetime(2026, 4, 3, 10, 0, 0),
            close=1800.50,
            open=1800.00,
            high=1801.00,
            low=1799.50,
            volume=100.0,
        )
        assert snapshot.symbol == "XAUUSD"
        assert snapshot.bid == 1800.50
        assert snapshot.ask == 1800.55

    def test_market_snapshot_invalid_bid_ask(self):
        """Test MarketSnapshot validation rejects invalid bid/ask."""
        with pytest.raises(ValueError, match="Ask price.*must be greater than bid"):
            MarketSnapshot(
                symbol="XAUUSD",
                timeframe=5,
                digits=2,
                magic_number=20260313,
                bid=1800.55,  # bid > ask
                ask=1800.50,
                ema_fast=1801.20,
                ema_slow=1799.80,
                atr14=18.0,
                spread_points=5.0,
                last_closed_bar_time=datetime(2026, 4, 3, 10, 0, 0),
                close=1800.50,
                open=1800.00,
                high=1801.00,
                low=1799.50,
                volume=100.0,
            )


class TestProtectionStateValidation:
    """Tests for ProtectionState validation."""

    def test_protection_state_validation(self):
        """Test ProtectionState post-init validation."""
        protection = ProtectionState(
            protection_stage=ProtectionStage.STAGE1,
            entry_price=1800.50,
            entry_atr=18.0,
        )
        assert protection.protection_stage == ProtectionStage.STAGE1
        assert protection.entry_price == 1800.50

    def test_protection_state_invalid_entry_price(self):
        """Test ProtectionState validation rejects invalid entry price."""
        with pytest.raises(ValueError, match="Entry price must be positive"):
            ProtectionState(
                protection_stage=ProtectionStage.STAGE1,
                entry_price=0.0,  # Invalid
                entry_atr=18.0,
            )


if __name__ == "__main__":
    pytest.main([__file__])
