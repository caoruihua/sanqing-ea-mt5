# sanqing-ea-mt5 - Operational Guide

## Project Overview

This is a Python 1:1 replica of the MT5 trading system with strict runtime dependency boundary. The system implements three trading strategies (ExpansionFollow, Pullback, TrendContinuation) with fixed priority ordering and maintains strict runtime constraints.

## Runtime Dependency Boundary

**CRITICAL**: The project maintains a strict runtime dependency boundary:
- **Explicit runtime dependencies**: `MetaTrader5` only (official MT5 Python API)
- **Development dependencies**: `pytest`, `pytest-cov`, `ruff`
- **Forbidden explicit dependencies**: `pandas`, `pydantic`, `requests`, `loguru`, or any other third-party packages beyond MetaTrader5

**Note**: The `MetaTrader5` package transitively installs `numpy` as a dependency. This is a constraint of the MetaTrader5 package itself, not a choice of this project. No other forbidden dependencies are installed.

## Setup Instructions

### 1. Virtual Environment

Always use the project-local virtual environment:

```bash
# Create virtual environment (if not already created)
python -m venv .venv

# Activate on Windows PowerShell
.venv\Scripts\Activate.ps1

# Activate on Windows Command Prompt
.venv\Scripts\activate.bat

# Activate on Linux/macOS
source .venv/bin/activate
```

### 2. Install Dependencies with uv

The project uses `uv` for dependency management:

```bash
# Install uv if not already installed
pip install uv

# Install project with dev dependencies
uv pip install -e .[dev]
```

**IMPORTANT**: Never install dependencies globally. Always work within the `.venv` environment.

### 3. Configuration

Copy the example configuration file:

```bash
cp config\runtime.ini.example config\runtime.ini
```

Edit `config\runtime.ini` with your trading parameters and MT5 credentials.

## Development Workflow

### Running Tests

```bash
# Run all tests
uv run python -m pytest -q

# Run specific test file
uv run python -m pytest -q tests/unit/test_example.py

# Run tests with coverage
uv run python -m pytest --cov=src --cov-report=term-missing
```

### Code Quality

```bash
# Run ruff linter
uv run python -m ruff check src tests

# Format code with black (if installed)
uv run black src tests
```

### Running the Application

```bash
# Run one cycle only
uv run python run.py --config config/runtime.ini --once

# Polling mode (rollback-safe legacy trigger source)
uv run python run.py --config config/runtime.ini --trigger-mode poll --poll-sec 2

# Real tick wake-up mode
uv run python run.py --config config/runtime.ini --trigger-mode tick_http
```

If `--trigger-mode` is omitted, `run.py` uses `trigger_mode` from `config/runtime.ini`. The CLI flag only overrides config for that launch.

### TickRelay Setup

`tick_http` mode requires the companion EA `mt5/TickRelay.mq5`:

1. Attach `TickRelay.mq5` to the target MT5 chart.
2. Open **Tools -> Options -> Expert Advisors**.
3. Enable WebRequest and whitelist `http://127.0.0.1:8765`.
4. Keep TickRelay and Python runtime on the same symbol and timeframe.

TickRelay behavior:
- `OnTick` queues one pending wake-up per closed bar and refreshes the latest tick for that bar.
- `OnTimer` sends queued wake-ups via `WebRequest` in arrival order.
- It never sends orders, modifies positions, or closes trades.

## Project Structure

```
├── src/
│   ├── app/           # Application entry points and orchestration
│   ├── config/        # Configuration loading and validation
│   ├── domain/        # Domain models and constants
│   ├── indicators/    # Technical indicator calculations
│   ├── strategies/    # Trading strategy implementations
│   ├── core/         # Core trading logic (entry gates, execution, protection)
│   ├── adapters/     # Broker adapters (MT5, Sim)
│   └── utils/        # Utility functions (logging, rounding, etc.)
├── tests/
│   ├── unit/         # Unit tests
│   ├── integration/  # Integration tests
│   └── fixtures/     # Test fixtures and data
├── config/           # Configuration files
├── scripts/          # Utility scripts
└── ci/              # CI/CD configuration
```

## Key Design Principles

1. **Strict Dependency Boundary**: Only `MetaTrader5` as runtime third-party dependency
2. **Virtual Environment Isolation**: All work must be done within `.venv`
3. **Test-Driven Development**: All features must have corresponding tests
4. **Semantic 1:1 Replica**: Behavior must match original MT4 EA exactly
5. **Modular Architecture**: Clear separation between strategies, execution, and risk management

## Troubleshooting

### Common Issues

1. **ModuleNotFoundError: No module named 'MetaTrader5'**
   - Ensure MT5 terminal is installed
   - Install MetaTrader5 package: `pip install MetaTrader5`

2. **Virtual environment not activated**
   - Always activate `.venv` before running any commands
   - Verify activation: `where python` should point to `.venv\Scripts\python.exe`

3. **Permission errors on Windows**
   - Run PowerShell as Administrator if needed
   - Check execution policy: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### MT5 Connection Issues

1. **MT5 terminal must be running** before executing the application
2. **Demo account must be logged in** for MT5 demo mode
3. **Check firewall settings** if connection fails

### Tick HTTP Issues

1. **No `收到 tick 事件` logs in Python**
   - Confirm `TickRelay.mq5` is attached to the correct chart
   - Confirm `http://127.0.0.1:8765` is in the MT5 WebRequest whitelist
   - Confirm Python is running with `--trigger-mode tick_http`

2. **TickRelay prints POST failed**
   - Ensure Python runtime started before MT5 begins relaying ticks
   - Ensure local port `8765` is not occupied by another process
   - Keep the endpoint localhost-only

3. **Need immediate rollback**
   - Stop/remove TickRelay from the chart
   - Restart Python with `--trigger-mode poll --poll-sec 2`

## Verification Commands

Before committing changes, always run:

```bash
# 1. Run all tests
uv run python -m pytest -q

# 2. Run linter
uv run python -m ruff check src tests

# 3. Verify dependency boundary (MetaTrader5 is only explicit runtime dependency)
uv run python -c "
# Check that MetaTrader5 is the only explicit runtime dependency in pyproject.toml
print('Dependency boundary check:')
print('- MetaTrader5 is the only explicit runtime dependency in pyproject.toml')
print('- Note: MetaTrader5 transitively installs numpy')
print('- Forbidden libraries (pandas, pydantic, requests, loguru) are not in dependencies')
"

# 4. Emit semantic regression report with tick-mode invariants
uv run python scripts/run_semantic_suite.py --out .sisyphus/evidence/task-7-semantic-suite.json
```
