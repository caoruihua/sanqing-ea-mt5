# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based MT5 trading signal system that reads market data from a local MetaTrader 5 terminal, analyzes three trading strategies, and sends order instructions back to MT5. The system does NOT manage the MT5 account (login/logout) - the user must manually open and log into MT5 before running this system.

## Common Commands

### Running the Application

```bash
# Run one analysis cycle (recommended for testing)
uv run python run.py --config config/runtime.ini --once

# Polling mode - continuously poll MT5 every N seconds
uv run python run.py --config config/runtime.ini --trigger-mode poll --poll-sec 2

# Tick HTTP mode - wait for tick events from MT5 TickRelay EA
uv run python run.py --config config/runtime.ini --trigger-mode tick_http

# Test order linkage (sends 0.01 test order and immediately closes)
uv run python run.py --config config/runtime.ini --test-order
```

### Testing and Linting

```bash
# Run all tests
uv run python -m pytest -q

# Run specific test file
uv run python -m pytest -q tests/unit/test_example.py

# Run linter
uv run python -m ruff check src tests
```

## Development Workflow Rules

**Required for every task:**

1. After completing code changes, run unit tests to verify: `uv run python -m pytest -q`
2. Ensure all tests pass before proceeding
3. Delete any temporary files created during the task
4. **After self-testing is complete, delete the test files you created (keep only production code)**
5. Only mark the task as complete after tests pass and cleanup is done

### Setup

```bash
# Create and activate virtual environment (Windows)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
uv pip install -e .[dev]
```

## High-Level Architecture

### Core Data Flow

```
MT5 Terminal (K-line/Quote)
    ↓
ContextBuilder.build_snapshot() → MarketSnapshot
    ↓
Orchestrator.process_snapshot()
    ├── DailyRiskController.update()    # Check daily profit/loss limits
    ├── ProtectionEngine.evaluate()      # Update SL/TP for open positions
    ├── StrategySelector.select()        # Choose highest priority signal
    ├── EntryGate.evaluate()             # Validate entry conditions
    └── ExecutionEngine.submit()         # Send order via MT5BrokerAdapter
        ↓
    MT5 Terminal (order execution)
```

### Strategy Priority (Fixed Order)

Strategies are evaluated in strict priority - only the highest priority signal is taken:

1. **ExpansionFollow** - Explosive breakout with volume expansion
2. **Pullback** - EMA retracement with rejection pattern
3. **TrendContinuation** - Trend-following breakout

### Key Architectural Constraints

**Single Position Constraint**: Only one position per `symbol + magic_number` combination. The system checks `broker.get_position()` before sending any new order.

**Closed-Bar-Only Decisions**: All strategies only analyze fully closed candles (`last_closed_bar_time`). No decisions are made on forming candles.

**State Persistence**: Runtime state (position info, daily stats, protection state) is persisted to `state/runtime_state.json` atomically. The system supports restart recovery via `load_and_reconcile()`.

**Two-Stage Protection**: Open positions have dynamic SL/TP management:
- Stage 1 (1.0x ATR): Move SL to breakeven + small buffer
- Stage 2 (1.5x ATR): Activate trailing stop

**Strict Dependency Boundary**: Only `MetaTrader5` is allowed as an explicit runtime dependency. The `MetaTrader5` package transitively installs `numpy`, but no other third-party libraries (pandas, pydantic, requests, etc.) are permitted.

### Key Files and Responsibilities

| File | Responsibility |
|------|----------------|
| `src/app/orchestrator.py` | Main coordinator - wires all components together |
| `src/core/strategy_selector.py` | Priority-based strategy selection |
| `src/core/entry_gate.py` | Entry validation (new bar check, volatility filter, position check) |
| `src/core/execution_engine.py` | Order execution with retry logic |
| `src/core/protection_engine.py` | Dynamic SL/TP management for open positions |
| `src/core/context_builder.py` | Builds MarketSnapshot from MT5 bar data |
| `src/adapters/mt5_broker.py` | Thin wrapper around MT5 official Python API |

### Configuration

Main config at `config/runtime.ini`:
- `[symbol]` - Trading symbol (default: XAUUSD)
- `[timeframe]` - Candle timeframe in minutes (default: 5)
- `[magic]` - Magic number for order identification
- `[trading]` - Lot size, slippage, max retries
- `[daily_limits]` - Max trades per day, daily profit stop

### Trigger Modes

**Poll Mode** (`trigger_mode = poll`): Python actively queries MT5 for new closed bars at fixed intervals.

**Tick HTTP Mode** (`trigger_mode = tick_http`): Python HTTP server waits for `mt5/TickRelay.mq5` EA to push tick events. Requires:
1. TickRelay.mq5 attached to MT5 chart
2. `http://127.0.0.1:8765` in MT5 WebRequest whitelist
3. Same symbol/timeframe on both sides

### Log Output

Structured JSON logs written to `logs/runtime.log` and console:
- `strategy_select_started` - Market data snapshot at decision time
- `strategy_can_trade` / `strategy_no_signal` - Per-strategy evaluation
- `order_submit_started` / `order_filled` / `order_rejected` - Execution flow
- `protection_modified` - Dynamic SL/TP updates

Console logs are also written to `logs/console/` with hourly rotation.
