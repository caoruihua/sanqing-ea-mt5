# Bare-K Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 4-strategy indicator-heavy system with a single naked-K strategy using hard TP, no SL, and a 1-hour cooldown.

**Architecture:** Strip all indicator computation from ContextBuilder, introduce BareKStrategy (consecutive N-bar direction), update EntryGate with cooldown, and modify ExecutionEngine to calculate broker TP price from a $10 USD profit target.

**Tech Stack:** Python 3.12, MetaTrader5, pytest, ruff

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/domain/models.py` | Modify | Prune MarketSnapshot; add `last_trade_close_time` to RuntimeState; add `profit_target_usd` to SignalDecision |
| `src/domain/constants.py` | Modify | Add `COOLDOWN_ACTIVE` to RejectionReason; add `DEFAULT_CONSECUTIVE_BARS = 3` |
| `src/strategies/bare_k.py` | Create | Single strategy: consecutive N same-direction bars |
| `src/core/context_builder.py` | Modify | Remove all indicators; keep only raw candle history |
| `src/core/strategy_selector.py` | Modify | Replace 4-strategy list with `[BareKStrategy]` |
| `src/core/entry_gate.py` | Modify | Add cooldown check; remove volatility filter |
| `src/core/execution_engine.py` | Modify | Allow `sl=0`; add $10 USD → TP price calculation |
| `src/core/orchestrator.py` | Modify | Update `last_trade_close_time` on position close detection |
| `tests/unit/strategies/test_bare_k.py` | Create | Unit tests for BareKStrategy |
| `tests/unit/core/test_entry_gate.py` | Create | Unit tests for cooldown gate |
| `tests/unit/core/test_execution_engine.py` | Create | Unit tests for TP calculation and sl=0 allowance |
| `tests/unit/core/test_context_builder.py` | Create | Unit tests for simplified builder |

---

## Task 1: Domain Model Updates

**Files:**
- Modify: `src/domain/models.py`
- Modify: `src/domain/constants.py`

- [ ] **Step 1: Update MarketSnapshot**

Remove indicator fields from `MarketSnapshot`. Replace with raw candle history lists.

In `src/domain/models.py`, replace the `MarketSnapshot` dataclass (keep `bid`, `ask`, `spread_points`, `last_closed_bar_time`, `symbol`, `timeframe`, `digits`, `magic_number`) and add:

```python
@dataclass
class MarketSnapshot:
    symbol: str
    timeframe: int
    digits: int
    magic_number: int
    bid: float
    ask: float
    spread_points: float
    last_closed_bar_time: datetime

    # Current bar
    close: float
    open: float
    high: float
    low: float

    # Candle history (last N+1 bars, oldest first, current last)
    opens_history: List[float] = field(default_factory=list)
    closes_history: List[float] = field(default_factory=list)
    highs_history: List[float] = field(default_factory=list)
    lows_history: List[float] = field(default_factory=list)

    def __post_init__(self):
        if self.bid <= 0:
            raise ValueError(f"Bid price must be positive: {self.bid}")
        if self.ask <= 0:
            raise ValueError(f"Ask price must be positive: {self.ask}")
        if self.ask <= self.bid:
            raise ValueError(f"Ask price ({self.ask}) must be greater than bid ({self.bid})")
        if self.spread_points < 0:
            raise ValueError(f"Spread points must be non-negative: {self.spread_points}")
```

Delete the old fields: `ema_fast`, `ema_slow`, `atr14`, `ema_fast_prev3`, `ema_slow_prev3`, `high_prev2`, `high_prev3`, `low_prev2`, `low_prev3`, `prev_open`, `prev_close`, `prev_high`, `prev_low`, `high_3`, `low_3`, `median_body_20`, `prev3_body_max`, `volume_ma_20`, `high_20`, `low_20`, `adx14`, `channel_width_ratio`.

- [ ] **Step 2: Add profit_target_usd to SignalDecision**

In `SignalDecision`, add a new field after `lots`:

```python
profit_target_usd: float = 10.0
```

And relax the `atr_value` check (bare-K does not use ATR):

```python
def __post_init__(self):
    if self.entry_price <= 0:
        raise ValueError(f"Entry price must be positive: {self.entry_price}")
    if self.lots <= 0:
        raise ValueError(f"Lot size must be positive: {self.lots}")
    if self.atr_value < 0:
        raise ValueError(f"ATR value must be non-negative: {self.atr_value}")
```

- [ ] **Step 3: Add last_trade_close_time to RuntimeState**

In `RuntimeState`, add after `position_strategy`:

```python
last_trade_close_time: Optional[datetime] = None
```

Update `to_dict` / `from_dict` to handle the new datetime field (follow the same pattern used for `last_entry_bar_time`).

In `to_dict` conversion, the datetime converter already handles all datetime fields generically through `convert_value`, so no change needed there.

In `from_dict`, add `"last_trade_close_time"` to the list of datetime keys:

```python
if key in [
    "last_entry_bar_time",
    "last_processed_bar_time",
    "stage1_activated_at",
    "stage2_activated_at",
    "last_trade_close_time",
]:
```

- [ ] **Step 4: Add COOLDOWN_ACTIVE to RejectionReason**

In `src/domain/constants.py`, add inside `RejectionReason`:

```python
COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
```

Also add:

```python
DEFAULT_CONSECUTIVE_BARS = 3
```

- [ ] **Step 5: Commit**

```bash
git add src/domain/models.py src/domain/constants.py
git commit -m "refactor(domain): prune MarketSnapshot, add bare-K fields"
```

---

## Task 2: BareKStrategy

**Files:**
- Create: `src/strategies/bare_k.py`
- Create: `tests/unit/strategies/test_bare_k.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/strategies/test_bare_k.py`:

```python
from datetime import datetime

import pytest

from src.domain.models import MarketSnapshot, OrderType, RuntimeState
from src.strategies.bare_k import BareKStrategy


def _make_snapshot(closes, opens) -> MarketSnapshot:
    return MarketSnapshot(
        symbol="XAUUSD",
        timeframe=5,
        digits=2,
        magic_number=123,
        bid=closes[-1] - 0.1,
        ask=closes[-1] + 0.1,
        spread_points=10.0,
        last_closed_bar_time=datetime.now(),
        close=closes[-1],
        open=opens[-1],
        high=max(closes[-1], opens[-1]) + 0.5,
        low=min(closes[-1], opens[-1]) - 0.5,
        opens_history=opens,
        closes_history=closes,
        highs_history=[max(c, o) + 0.5 for c, o in zip(closes, opens)],
        lows_history=[min(c, o) - 0.5 for c, o in zip(closes, opens)],
    )


def test_three_bullish_bars_generates_buy():
    opens = [1900.0, 1901.0, 1902.0]
    closes = [1901.0, 1902.0, 1903.0]
    snapshot = _make_snapshot(closes, opens)
    state = RuntimeState(day_key="2026.05.15")
    strategy = BareKStrategy(consecutive_bars=3, fixed_lots=0.01)

    assert strategy.can_trade(snapshot, state) is True
    intent = strategy.build_intent(snapshot, state)
    assert intent is not None
    assert intent.order_type == OrderType.BUY
    assert intent.profit_target_usd == 10.0


def test_three_bearish_bars_generates_sell():
    opens = [1903.0, 1902.0, 1901.0]
    closes = [1902.0, 1901.0, 1900.0]
    snapshot = _make_snapshot(closes, opens)
    state = RuntimeState(day_key="2026.05.15")
    strategy = BareKStrategy(consecutive_bars=3, fixed_lots=0.01)

    intent = strategy.build_intent(snapshot, state)
    assert intent is not None
    assert intent.order_type == OrderType.SELL


def test_mixed_direction_returns_none():
    opens = [1900.0, 1901.0, 1902.0]
    closes = [1901.0, 1900.0, 1903.0]
    snapshot = _make_snapshot(closes, opens)
    state = RuntimeState(day_key="2026.05.15")
    strategy = BareKStrategy(consecutive_bars=3, fixed_lots=0.01)

    assert strategy.build_intent(snapshot, state) is None


def test_insufficient_history_returns_none():
    opens = [1900.0, 1901.0]
    closes = [1901.0, 1902.0]
    snapshot = _make_snapshot(closes, opens)
    state = RuntimeState(day_key="2026.05.15")
    strategy = BareKStrategy(consecutive_bars=3, fixed_lots=0.01)

    assert strategy.can_trade(snapshot, state) is False
    assert strategy.build_intent(snapshot, state) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/strategies/test_bare_k.py -v`

Expected: `ModuleNotFoundError: No module named 'src.strategies.bare_k'`

- [ ] **Step 3: Write minimal implementation**

Create `src/strategies/bare_k.py`:

```python
from typing import Optional

from src.domain.constants import DEFAULT_CONSECUTIVE_BARS, DEFAULT_FIXED_LOTS
from src.domain.models import MarketSnapshot, OrderType, RuntimeState, SignalDecision
from src.strategies.base import BaseStrategy


class BareKStrategy(BaseStrategy):
    """Naked K-line strategy: trade in the direction of N consecutive candles."""

    def __init__(self, consecutive_bars: int = DEFAULT_CONSECUTIVE_BARS, fixed_lots: float = DEFAULT_FIXED_LOTS) -> None:
        self.consecutive_bars = consecutive_bars
        self.fixed_lots = fixed_lots

    @property
    def name(self) -> str:
        return "BareK"

    def can_trade(self, snapshot: MarketSnapshot, state: RuntimeState) -> bool:
        _ = state
        return len(snapshot.closes_history) >= self.consecutive_bars

    def build_intent(self, snapshot: MarketSnapshot, state: RuntimeState) -> Optional[SignalDecision]:
        _ = state
        if not self.can_trade(snapshot, state):
            return None

        closes = snapshot.closes_history
        opens = snapshot.opens_history
        n = self.consecutive_bars

        # Check last N bars (current bar is the last element)
        last_closes = closes[-n:]
        last_opens = opens[-n:]

        bullish = all(c > o for c, o in zip(last_closes, last_opens))
        bearish = all(c < o for c, o in zip(last_closes, last_opens))

        if bullish:
            return SignalDecision(
                strategy_name=self.name,
                order_type=OrderType.BUY,
                entry_price=snapshot.ask,
                stop_loss=0.0,
                take_profit=None,
                atr_value=0.0,
                lots=self.fixed_lots,
                profit_target_usd=10.0,
                conditions_met=["consecutive_bullish"],
            )

        if bearish:
            return SignalDecision(
                strategy_name=self.name,
                order_type=OrderType.SELL,
                entry_price=snapshot.bid,
                stop_loss=0.0,
                take_profit=None,
                atr_value=0.0,
                lots=self.fixed_lots,
                profit_target_usd=10.0,
                conditions_met=["consecutive_bearish"],
            )

        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/strategies/test_bare_k.py -v`

Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/strategies/bare_k.py tests/unit/strategies/test_bare_k.py
git commit -m "feat(strategy): add BareKStrategy for naked-K trading"
```

---

## Task 3: ContextBuilder Simplification

**Files:**
- Modify: `src/core/context_builder.py`
- Create: `tests/unit/core/test_context_builder.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/core/test_context_builder.py`:

```python
from datetime import datetime

import pytest

from src.core.context_builder import ContextBuilder


def test_build_snapshot_returns_candle_history():
    builder = ContextBuilder(symbol="XAUUSD", timeframe=5, digits=2, magic_number=123)
    bars = [
        (datetime(2026, 1, 1, 12, 0), 1900.0, 1901.0, 1899.0, 1900.5, 100, 10, 100),
        (datetime(2026, 1, 1, 12, 5), 1900.5, 1901.5, 1900.0, 1901.0, 100, 10, 100),
        (datetime(2026, 1, 1, 12, 10), 1901.0, 1902.0, 1900.5, 1901.5, 100, 10, 100),
        (datetime(2026, 1, 1, 12, 15), 1901.5, 1902.5, 1901.0, 1902.0, 100, 10, 100),
    ]
    snapshot = builder.build_snapshot(bars, bid=1901.9, ask=1902.0)

    assert snapshot.symbol == "XAUUSD"
    assert snapshot.close == 1902.0
    assert snapshot.open == 1901.5
    assert snapshot.closes_history == [1900.5, 1901.0, 1901.5, 1902.0]
    assert snapshot.opens_history == [1900.0, 1900.5, 1901.0, 1901.5]
    assert snapshot.highs_history == [1901.0, 1901.5, 1902.0, 1902.5]
    assert snapshot.lows_history == [1899.0, 1900.0, 1900.5, 1901.0]


def test_build_snapshot_rejects_empty_bars():
    builder = ContextBuilder()
    with pytest.raises(ValueError, match="No bars provided"):
        builder.build_snapshot([], bid=1900.0, ask=1900.1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/core/test_context_builder.py -v`

Expected: FAIL (old builder still produces old snapshot shape / missing history fields)

- [ ] **Step 3: Simplify ContextBuilder**

Replace the body of `src/core/context_builder.py` with:

```python
"""
Build a minimal MarketSnapshot from raw MT5 bar data.
No indicators — only raw candle history for naked-K strategies.
"""

from datetime import datetime
from typing import List, Optional, Tuple

from src.domain.constants import DEFAULT_MAGIC_NUMBER, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME
from src.domain.models import MarketSnapshot

BarData = Tuple[
    datetime, float, float, float, float, int, int, int
]


class ContextBuilder:
    def __init__(
        self,
        symbol: str = DEFAULT_SYMBOL,
        timeframe: int = DEFAULT_TIMEFRAME,
        digits: int = 2,
        magic_number: int = DEFAULT_MAGIC_NUMBER,
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.digits = digits
        self.magic_number = magic_number

    def build_snapshot(self, bars: List[BarData], bid: float, ask: float) -> MarketSnapshot:
        if not bars:
            raise ValueError("No bars provided")
        if bid <= 0 or ask <= 0:
            raise ValueError(f"Bid/ask prices must be positive: bid={bid}, ask={ask}")
        if ask <= bid:
            raise ValueError(f"Ask price ({ask}) must be greater than bid ({bid})")

        times = [b[0] for b in bars]
        opens = [b[1] for b in bars]
        highs = [b[2] for b in bars]
        lows = [b[3] for b in bars]
        closes = [b[4] for b in bars]
        spreads = [b[6] for b in bars]

        last = len(bars) - 1
        return MarketSnapshot(
            symbol=self.symbol,
            timeframe=self.timeframe,
            digits=self.digits,
            magic_number=self.magic_number,
            bid=bid,
            ask=ask,
            spread_points=float(spreads[last]),
            last_closed_bar_time=times[last],
            close=closes[last],
            open=opens[last],
            high=highs[last],
            low=lows[last],
            opens_history=opens,
            closes_history=closes,
            highs_history=highs,
            lows_history=lows,
        )


def create_market_snapshot(
    bars: List[BarData],
    bid: float,
    ask: float,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: int = DEFAULT_TIMEFRAME,
    digits: int = 2,
    magic_number: int = DEFAULT_MAGIC_NUMBER,
) -> MarketSnapshot:
    builder = ContextBuilder(symbol=symbol, timeframe=timeframe, digits=digits, magic_number=magic_number)
    return builder.build_snapshot(bars, bid, ask)
```

Delete everything else in the file (all indicator methods, `InsufficientBarsError`, etc.).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/core/test_context_builder.py -v`

Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/context_builder.py tests/unit/core/test_context_builder.py
git commit -m "refactor(context_builder): strip indicators, keep raw candle history"
```

---

## Task 4: StrategySelector Update

**Files:**
- Modify: `src/core/strategy_selector.py`

- [ ] **Step 1: Replace strategy list**

In `src/core/strategy_selector.py`, replace the imports and `__init__`:

```python
from src.strategies.bare_k import BareKStrategy
```

Remove imports for `ExpansionFollowStrategy`, `PullbackStrategy`, `ReversalStrategy`, `TrendContinuationStrategy`.

In `__init__`, replace:

```python
self.strategies = strategies or [
    BareKStrategy(fixed_lots=fixed_lots),
]
```

- [ ] **Step 2: Commit**

```bash
git add src/core/strategy_selector.py
git commit -m "refactor(selector): switch to single BareKStrategy"
```

---

## Task 5: EntryGate Update

**Files:**
- Modify: `src/core/entry_gate.py`
- Create: `tests/unit/core/test_entry_gate.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/core/test_entry_gate.py`:

```python
from datetime import datetime, timedelta

import pytest

from src.core.entry_gate import EntryGate
from src.domain.constants import RejectionReason
from src.domain.models import MarketSnapshot, OrderType, RuntimeState, SignalDecision


def _make_signal() -> SignalDecision:
    return SignalDecision(
        strategy_name="BareK",
        order_type=OrderType.BUY,
        entry_price=1900.0,
        stop_loss=0.0,
        take_profit=None,
        atr_value=0.0,
        lots=0.01,
        profit_target_usd=10.0,
    )


def _make_snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="XAUUSD",
        timeframe=5,
        digits=2,
        magic_number=123,
        bid=1900.0,
        ask=1900.1,
        spread_points=10.0,
        last_closed_bar_time=datetime(2026, 1, 1, 12, 0),
        close=1900.0,
        open=1899.0,
        high=1901.0,
        low=1898.0,
        opens_history=[1899.0],
        closes_history=[1900.0],
        highs_history=[1901.0],
        lows_history=[1898.0],
    )


def test_cooldown_rejects_within_one_hour():
    gate = EntryGate(max_trades_per_day=30)
    state = RuntimeState(
        day_key="2026.01.01",
        last_trade_close_time=datetime(2026, 1, 1, 11, 30),
    )
    snapshot = _make_snapshot()
    snapshot.last_closed_bar_time = datetime(2026, 1, 1, 12, 0)

    result = gate.evaluate(
        signal=_make_signal(),
        snapshot=snapshot,
        state=state,
        has_existing_position=False,
        strategy_can_trade=True,
    )
    assert result.intent is None
    assert result.reason_code == RejectionReason.COOLDOWN_ACTIVE


def test_cooldown_passes_after_one_hour():
    gate = EntryGate(max_trades_per_day=30)
    state = RuntimeState(
        day_key="2026.01.01",
        last_trade_close_time=datetime(2026, 1, 1, 10, 0),
    )
    snapshot = _make_snapshot()
    snapshot.last_closed_bar_time = datetime(2026, 1, 1, 12, 0)

    result = gate.evaluate(
        signal=_make_signal(),
        snapshot=snapshot,
        state=state,
        has_existing_position=False,
        strategy_can_trade=True,
    )
    assert result.intent is not None
    assert result.reason_code is None


def test_no_cooldown_when_never_traded():
    gate = EntryGate(max_trades_per_day=30)
    state = RuntimeState(day_key="2026.01.01", last_trade_close_time=None)
    snapshot = _make_snapshot()

    result = gate.evaluate(
        signal=_make_signal(),
        snapshot=snapshot,
        state=state,
        has_existing_position=False,
        strategy_can_trade=True,
    )
    assert result.intent is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/core/test_entry_gate.py -v`

Expected: `AttributeError: type object 'RejectionReason' has no attribute 'COOLDOWN_ACTIVE'` or `COOLDOWN_ACTIVE` rejection not implemented

- [ ] **Step 3: Implement cooldown gate and remove volatility filter**

In `src/core/entry_gate.py`:

1. Add import:
```python
from datetime import timedelta
```

2. After the `EXISTING_POSITION` check, add:

```python
if state.last_trade_close_time is not None:
    elapsed = snapshot.last_closed_bar_time - state.last_trade_close_time
    if elapsed < timedelta(hours=1):
        reason = RejectionReason.COOLDOWN_ACTIVE
        self._log_rejection(strategy_name, reason, snapshot.symbol)
        return EntryGateResult(intent=None, reason_code=reason)
```

3. Remove the `_is_low_volatility` method and its call inside `evaluate`.

4. Update `EntryGate.__init__` to remove `low_vol_atr_points_floor` and `low_vol_atr_spread_ratio_floor` parameters (keep defaults for backward compat but ignore them).

```python
def __init__(
    self,
    max_trades_per_day: int = DEFAULT_MAX_TRADES_PER_DAY,
    logger: Optional[StructuredLogger] = None,
) -> None:
    self.max_trades_per_day = max_trades_per_day
    self.logger = logger
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/core/test_entry_gate.py -v`

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/entry_gate.py tests/unit/core/test_entry_gate.py
git commit -m "feat(entry_gate): add 1-hour cooldown, remove volatility filter"
```

---

## Task 6: ExecutionEngine Update

**Files:**
- Modify: `src/core/execution_engine.py`
- Create: `tests/unit/core/test_execution_engine.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/core/test_execution_engine.py`:

```python
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.core.execution_engine import ExecutionEngine
from src.domain.models import MarketSnapshot, OrderType, RuntimeState, SignalDecision, TradeIntent


def _make_intent(sl: float = 0.0, tp: float | None = None) -> TradeIntent:
    snapshot = MarketSnapshot(
        symbol="XAUUSD",
        timeframe=5,
        digits=2,
        magic_number=123,
        bid=1900.0,
        ask=1900.1,
        spread_points=10.0,
        last_closed_bar_time=datetime.now(),
        close=1900.0,
        open=1899.0,
        high=1901.0,
        low=1898.0,
        opens_history=[1899.0],
        closes_history=[1900.0],
        highs_history=[1901.0],
        lows_history=[1898.0],
    )
    signal = SignalDecision(
        strategy_name="BareK",
        order_type=OrderType.BUY,
        entry_price=1900.1,
        stop_loss=sl,
        take_profit=tp,
        atr_value=0.0,
        lots=0.01,
        profit_target_usd=10.0,
    )
    return TradeIntent(signal_decision=signal, market_snapshot=snapshot, action_id="test-001")


def test_validate_allows_zero_sl():
    broker = MagicMock()
    broker.get_position.return_value = None
    engine = ExecutionEngine(broker=broker)
    intent = _make_intent(sl=0.0)
    error = engine._validate_order_params(intent)
    assert error is None


def test_calculate_tp_price_for_buy():
    broker = MagicMock()
    engine = ExecutionEngine(broker=broker)

    # Mock symbol_info: tick_value=1.0, tick_size=0.01
    mock_info = MagicMock()
    mock_info.trade_tick_value = 1.0
    mock_info.trade_tick_size = 0.01

    tp = engine._calculate_tp_price(
        symbol="XAUUSD",
        order_type="BUY",
        entry_price=1900.0,
        volume=0.01,
        profit_target_usd=10.0,
        symbol_info=mock_info,
    )
    # 10 USD / (0.01 lot * 1.0 tick_value) = 1000 ticks
    # 1000 ticks * 0.01 tick_size = 10.0 price distance
    assert tp == 1910.0


def test_calculate_tp_price_for_sell():
    broker = MagicMock()
    engine = ExecutionEngine(broker=broker)

    mock_info = MagicMock()
    mock_info.trade_tick_value = 1.0
    mock_info.trade_tick_size = 0.01

    tp = engine._calculate_tp_price(
        symbol="XAUUSD",
        order_type="SELL",
        entry_price=1900.0,
        volume=0.01,
        profit_target_usd=10.0,
        symbol_info=mock_info,
    )
    assert tp == 1890.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/core/test_execution_engine.py -v`

Expected: `AttributeError` on `_calculate_tp_price` and validation failure for `sl=0`

- [ ] **Step 3: Implement changes**

In `src/core/execution_engine.py`:

1. Update `_validate_order_params` to allow `sl=0`:

```python
def _validate_order_params(self, intent: TradeIntent) -> Optional[str]:
    signal = intent.signal_decision

    if signal.entry_price <= 0:
        return f"Invalid entry_price: {signal.entry_price}"

    # Allow sl=0 (no stop loss)
    if signal.stop_loss < 0:
        return f"Invalid stop_loss: {signal.stop_loss}"

    if signal.take_profit is not None and signal.take_profit <= 0:
        return f"Invalid take_profit: {signal.take_profit}"

    if signal.lots <= 0:
        return f"Invalid lots: {signal.lots}"

    if signal.order_type.value == "BUY":
        if signal.stop_loss > 0 and signal.stop_loss >= signal.entry_price:
            return f"BUY stop_loss ({signal.stop_loss}) must be below entry ({signal.entry_price})"
        if signal.take_profit is not None and signal.take_profit <= signal.entry_price:
            return f"BUY take_profit ({signal.take_profit}) must be above entry ({signal.entry_price})"
    else:  # SELL
        if signal.stop_loss > 0 and signal.stop_loss <= signal.entry_price:
            return f"SELL stop_loss ({signal.stop_loss}) must be above entry ({signal.entry_price})"
        if signal.take_profit is not None and signal.take_profit >= signal.entry_price:
            return f"SELL take_profit ({signal.take_profit}) must be below entry ({signal.entry_price})"

    return None
```

2. Add `_calculate_tp_price` method:

```python
@staticmethod
def _calculate_tp_price(
    symbol: str,
    order_type: str,
    entry_price: float,
    volume: float,
    profit_target_usd: float,
    symbol_info,
) -> float:
    """Convert a USD profit target into a broker TP price."""
    tick_value = float(getattr(symbol_info, "trade_tick_value", 0.0))
    tick_size = float(getattr(symbol_info, "trade_tick_size", 0.0))

    if tick_value <= 0 or tick_size <= 0:
        raise ValueError(f"Invalid tick info for {symbol}: tick_value={tick_value}, tick_size={tick_size}")

    ticks_needed = profit_target_usd / (volume * tick_value)
    price_distance = ticks_needed * tick_size

    if order_type == "BUY":
        return entry_price + price_distance
    return entry_price - price_distance
```

3. Modify `submit` to compute TP before sending the order:

Inside `submit`, after validation and before the retry loop, add:

```python
# Calculate hard TP from profit_target_usd
profit_target = intent.signal_decision.profit_target_usd
symbol_info = None
if profit_target > 0:
    try:
        mt5 = importlib.import_module("MetaTrader5")
        symbol_info = mt5.symbol_info(snapshot.symbol)
    except Exception:
        pass

    if symbol_info is None:
        if self.logger is not None:
            self.logger.error(
                "order_symbol_info_failed",
                策略名称=strategy_name,
                品种=snapshot.symbol,
            )
        return {"success": False, "reason": "SYMBOL_INFO_UNAVAILABLE"}

    try:
        tp_price = self._calculate_tp_price(
            symbol=snapshot.symbol,
            order_type=order_type,
            entry_price=intent.signal_decision.entry_price,
            volume=intent.signal_decision.lots,
            profit_target_usd=profit_target,
            symbol_info=symbol_info,
        )
    except ValueError as exc:
        if self.logger is not None:
            self.logger.error(
                "order_tp_calculation_failed",
                策略名称=strategy_name,
                品种=snapshot.symbol,
                错误=str(exc),
            )
        return {"success": False, "reason": f"TP_CALCULATION_FAILED: {exc}"}
else:
    tp_price = intent.signal_decision.take_profit
```

Then update the `send_order` call to use `tp=tp_price`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/core/test_execution_engine.py -v`

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/execution_engine.py tests/unit/core/test_execution_engine.py
git commit -m "feat(execution): add $10 hard TP calculation, allow sl=0"
```

---

## Task 7: Orchestrator Update

**Files:**
- Modify: `src/core/orchestrator.py`

- [ ] **Step 1: Update position close detection**

In `src/core/orchestrator.py`, inside `_detect_position_close`, after clearing `last_position_ticket`, add the cooldown timestamp:

```python
# 清除历史持仓记录
if last_ticket is not None and position is None:
    # ... existing close logging ...

    # 记录平仓时间用于冷却期
    self.state.last_trade_close_time = snapshot.last_closed_bar_time

    # 清除历史持仓记录
    self.state.last_position_ticket = None
```

Make sure this line is added **before** the `last_position_ticket = None` reset.

- [ ] **Step 2: Commit**

```bash
git add src/core/orchestrator.py
git commit -m "feat(orchestrator): record last_trade_close_time on position close"
```

---

## Task 8: Cleanup & Validation

**Files:**
- All modified files

- [ ] **Step 1: Run linter**

Run: `uv run python -m ruff check src`

Expected: No errors (or only pre-existing ones unrelated to this change).

- [ ] **Step 2: Run all tests**

Run: `uv run python -m pytest tests/unit -v`

Expected: All newly added tests PASS.

- [ ] **Step 3: Smoke test (optional but recommended)**

Run a single cycle in `--once` mode to verify the full pipeline still assembles correctly:

```bash
uv run python run.py --config config/runtime.ini --once
```

(Requires MT5 to be running and logged in.)

- [ ] **Step 4: Final commit**

```bash
git commit -m "refactor(system): complete bare-K rewrite — single strategy, hard TP, no SL, cooldown"
```

---

## Plan Self-Review

### Spec Coverage

| Spec Requirement | Plan Task |
|------------------|-----------|
| BareKStrategy (consecutive N bars) | Task 2 |
| No stop loss (sl=0) | Task 6 (validation change) |
| Hard TP ($10 USD) | Task 6 (TP calculation) |
| 1-hour cooldown | Task 5 |
| Max lot 0.1 | Handled by config / gate (existing) |
| Single position only | Task 5 (existing gate preserved) |
| ContextBuilder stripped of indicators | Task 3 |
| StrategySelector single strategy | Task 4 |
| Orchestrator cooldown timestamp | Task 7 |

### Placeholder Scan

- No TBD/TODO in plan.
- No "add appropriate error handling" vague steps.
- All code blocks contain complete implementation.
- No "similar to Task N" shortcuts.

### Type Consistency

- `MarketSnapshot` fields match between Task 1 and Task 2/3/5/6.
- `SignalDecision.profit_target_usd` created in Task 1, used in Task 2 and Task 6.
- `RuntimeState.last_trade_close_time` created in Task 1, used in Task 5 and Task 7.
- `RejectionReason.COOLDOWN_ACTIVE` added in Task 1, used in Task 5.

Plan is complete and ready for execution.
