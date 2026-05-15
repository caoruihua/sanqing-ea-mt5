# Bare-K Rewrite Design

**Date:** 2026-05-15  
**Scope:** Replace the current 4-strategy indicator-heavy system with a single naked-K (price-action) strategy.  
**Status:** Approved

---

## 1. Goal

Remove all technical indicators (EMA, ATR, ADX, volume, etc.) and replace the existing strategy layer with a single **BareKStrategy** that makes directional decisions based solely on raw candlestick closes and opens.

## 2. Core Rules (User-Defined)

| Rule | Value |
|------|-------|
| Signal logic | Continuous `N` candles in the same direction (default `N = 3`) |
| Stop loss | **None** (`sl = 0`) |
| Take profit | Hard TP calculated so that profit = **$10 USD** at order open |
| Cool-down | Minimum **1 hour** between the previous close and the next open |
| Position limit | Only one position at a time (no new entry while a position exists) |
| Max lot size | **0.1** |

## 3. Signal Logic (BareKStrategy)

### 3.1 Input
- `MarketSnapshot` containing the last `N + 1` closed candles.
- Required history arrays: `opens_history`, `closes_history` (length ≥ `N + 1`).

### 3.2 Decision
```
IF   last N candles all have close > open  → LONG signal
ELIF last N candles all have close < open  → SHORT signal
ELSE                                       → NO SIGNAL
```

### 3.3 Output
- `SignalDecision` with:
  - `order_type`: BUY or SELL
  - `entry_price`: current ask (BUY) or bid (SELL)
  - `stop_loss`: `0.0` (explicitly disabled)
  - `take_profit`: `None` (calculated later by ExecutionEngine)
  - `profit_target_usd`: `10.0`
  - `lots`: user-configured fixed lots (capped at `0.1`)

## 4. Hard TP Calculation (ExecutionEngine)

Since the broker (MT5) requires a price-level TP, the engine must translate `$10` into a price distance.

### 4.1 Formula
```python
profit_target_usd = 10.0
volume            = signal.lots

symbol_info       = mt5.symbol_info(symbol)
tick_value        = symbol_info.trade_tick_value  # USD per tick per 1.0 lot
tick_size         = symbol_info.trade_tick_size   # price increment of 1 tick

ticks_needed      = profit_target_usd / (volume * tick_value)
price_distance    = ticks_needed * tick_size

if BUY:  tp = entry_price + price_distance
if SELL: tp = entry_price - price_distance
```

### 4.2 Validation Changes
- `ExecutionEngine._validate_order_params` must **skip** the `stop_loss > 0` check when `stop_loss == 0.0`.
- If `symbol_info` is unavailable, the order is rejected with reason `SYMBOL_INFO_UNAVAILABLE`.
- If the calculated TP violates the broker’s `STOP_LEVEL` (minimum distance), `send_order` returns `INVALID_STOPS` and the engine treats it as non-retryable.

## 5. Cool-Down Gate (EntryGate)

### 5.1 State Addition
- `RuntimeState.last_trade_close_time: Optional[datetime] = None`

### 5.2 Gate Check
Inserted into `EntryGate.evaluate` **after** the `EXISTING_POSITION` check:
```python
if state.last_trade_close_time is not None:
    elapsed = snapshot.last_closed_bar_time - state.last_trade_close_time
    if elapsed < timedelta(hours=1):
        return reject(RejectionReason.COOLDOWN_ACTIVE)
```

### 5.3 Reset Behavior
- **Not** reset on new trading day; the 1-hour limit is a physical-time constraint.
- Set by `Orchestrator._detect_position_close` when a position disappearance is detected.

## 6. ContextBuilder Simplification

### 6.1 Removed from MarketSnapshot
- `ema_fast`, `ema_slow`, `atr14`, `adx14`
- `ema_fast_prev3`, `ema_slow_prev3`
- `high_prev2`, `high_prev3`, `low_prev2`, `low_prev3`
- `median_body_20`, `prev3_body_max`, `volume_ma_20`, `high_20`, `low_20`
- `channel_width_ratio`

### 6.2 Added to MarketSnapshot
- `opens_history: List[float]`  — last `N + 1` opens
- `closes_history: List[float]` — last `N + 1` closes
- `highs_history: List[float]`  — last `N + 1` highs (for logging / future extension)
- `lows_history: List[float]`   — last `N + 1` lows (for logging / future extension)

### 6.3 Removed from ContextBuilder
All indicator calculation methods and their helper methods are deleted. The builder now only:
1. Validates `bid` / `ask`.
2. Splits the raw bar tuples into `opens`, `highs`, `lows`, `closes`.
3. Packs the most recent `N + 1` values into `MarketSnapshot`.

## 7. Orchestrator Changes

### 7.1 Position Close Detection
When `broker.get_position()` returns `None` but `state.last_position_ticket` was set:
```python
state.last_trade_close_time = snapshot.last_closed_bar_time
# ... existing close logging ...
```

### 7.2 Strategy Selector
Replace the 4-strategy list with a single instance:
```python
strategies = [BareKStrategy(consecutive_bars=N, fixed_lots=lots)]
```

## 8. Data Flow (Final)

```
MT5 Terminal (raw closed bars)
    ↓
ContextBuilder (split bars, no indicators)
    ↓
MarketSnapshot (symbol, bid, ask, spread, last N+1 candles)
    ↓
Orchestrator.process_snapshot()
    ├── DailyRiskController.update()      # optional, can be disabled
    ├── ProtectionEngine.evaluate()       # no-op (no SL/TP to modify)
    ├── StrategySelector.select()         # BareKStrategy only
    ├── EntryGate.evaluate()              # + cool-down check, - volatility filter
    └── ExecutionEngine.submit()          # calc $10 TP, sl=0, send order
        ↓
    MT5 Terminal (position open with hard TP)
```

## 9. Module Change Summary

| File | Action | Details |
|------|--------|---------|
| `src/strategies/bare_k.py` | **Create** | `BareKStrategy` implementing naked-K logic |
| `src/core/strategy_selector.py` | Modify | Replace 4-strategy list with `[BareKStrategy]` |
| `src/core/entry_gate.py` | Modify | Add cool-down gate; remove volatility filter |
| `src/core/execution_engine.py` | Modify | Allow `sl=0`; add `$10` → TP price calculation |
| `src/core/orchestrator.py` | Modify | Update `last_trade_close_time` on close detection |
| `src/core/context_builder.py` | Modify | Strip all indicators; keep only raw candle history |
| `src/domain/models.py` | Modify | Prune `MarketSnapshot`; add `last_trade_close_time` to `RuntimeState`; add `profit_target_usd` to `SignalDecision` |
| `src/core/daily_risk_controller.py` | **Optional** | Can be disabled or left as-is |
| `src/core/protection_engine.py` | **Optional** | Kept for state tracking but no longer modifies SL/TP |

## 10. Risks & Notes

- **No stop loss**: Maximum loss is unbounded. A sudden gap against the position can result in losses far exceeding $10.
- **Hard TP reliance**: The TP order lives on the broker server. If the server rejects it due to `STOP_LEVEL` constraints, the trade opens without any exit mechanism.
- **Cool-down edge case**: If the system restarts within the 1-hour window, `last_trade_close_time` is restored from `runtime_state.json`, so the cool-down is preserved correctly.
- **N configurability**: `N` (consecutive bars) should be configurable via `config/runtime.ini` or constants, defaulting to `3`.

---

*Design approved by user on 2026-05-15.*
