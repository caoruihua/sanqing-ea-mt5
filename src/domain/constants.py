"""
Trading system constants and default parameters.

All magic numbers, thresholds, and configuration defaults are defined here
to ensure consistency across the system.
"""

# Magic number for order identification (must match StrategySelector.mq4)
DEFAULT_MAGIC_NUMBER = 20260313

# Trading symbol and timeframe
DEFAULT_SYMBOL = "XAUUSD"
DEFAULT_TIMEFRAME = 5  # M5 in minutes

# Logging
DEFAULT_LOG_LEVEL = 1  # 0=off, 1=minimal, 2=verbose, 3=debug

# Daily risk limits
DEFAULT_MAX_TRADES_PER_DAY = 30
DEFAULT_DAILY_PROFIT_STOP_USD = 50.0

# Trading execution parameters
DEFAULT_FIXED_LOTS = 0.01
DEFAULT_SLIPPAGE = 30  # points
DEFAULT_MAX_RETRIES = 6

# Indicator parameters
DEFAULT_EMA_FAST_PERIOD = 9
DEFAULT_EMA_SLOW_PERIOD = 21
DEFAULT_ATR_PERIOD = 14

# Volatility filter thresholds
DEFAULT_LOW_VOL_ATR_POINTS_FLOOR = 300.0
DEFAULT_LOW_VOL_ATR_SPREAD_RATIO_FLOOR = 3.0

# Strategy-specific parameters
# TrendContinuation
TREND_CONTINUATION_ATR_MULTIPLIER_BREAKOUT = 0.20
TREND_CONTINUATION_ATR_MULTIPLIER_BODY = 0.35
TREND_CONTINUATION_INITIAL_SL_ATR = 1.2
TREND_CONTINUATION_INITIAL_TP_ATR = 2.0

# Pullback
PULLBACK_EMA_TOLERANCE_ATR = 0.15
PULLBACK_INITIAL_SL_ATR = 1.2
PULLBACK_INITIAL_TP_ATR = 2.0

# ExpansionFollow
EXPANSION_FOLLOW_BODY_ATR_MIN = 4.0
EXPANSION_FOLLOW_BODY_MEDIAN_RATIO_MIN = 2.20
EXPANSION_FOLLOW_BODY_PREV3_MAX_RATIO_MIN = 1.80
EXPANSION_FOLLOW_VOLUME_MA_RATIO_MIN = 1.90
EXPANSION_FOLLOW_BODY_RANGE_RATIO_MIN = 0.65
EXPANSION_FOLLOW_BREAKOUT_ATR_BUFFER = 0.10
EXPANSION_FOLLOW_STOP_LOSS_RANGE_RATIO = 0.6
EXPANSION_FOLLOW_INITIAL_TP_ATR = 2.0

# Protection engine parameters
PROTECTION_STAGE1_ATR_MULTIPLIER = 1.0
PROTECTION_STAGE1_SL_BUFFER_ATR = 0.1
PROTECTION_STAGE1_TP_ATR = 2.5

PROTECTION_STAGE2_ATR_MULTIPLIER = 1.5
PROTECTION_STAGE2_SL_DISTANCE_ATR = 0.9
PROTECTION_STAGE2_TP_DISTANCE_ATR = 0.8


# Entry gate rejection reason codes
# These codes are used in logs to indicate why an entry was blocked
class RejectionReason:
    """Entry gate rejection reasons."""

    # Core validation failures
    NOT_NEW_CLOSED_BAR = "NOT_NEW_CLOSED_BAR"
    DAILY_LOCKED = "DAILY_LOCKED"
    MAX_TRADES_EXCEEDED = "MAX_TRADES_EXCEEDED"
    EXISTING_POSITION = "EXISTING_POSITION"
    LOW_VOLATILITY = "LOW_VOLATILITY"

    # Strategy-specific failures
    NO_STRATEGY_SIGNAL = "NO_STRATEGY_SIGNAL"
    STRATEGY_CANNOT_TRADE = "STRATEGY_CANNOT_TRADE"

    # System failures
    INSUFFICIENT_BARS = "INSUFFICIENT_BARS"
    MARKET_CLOSED = "MARKET_CLOSED"
    CONNECTION_ERROR = "CONNECTION_ERROR"


# Priority ordering constants
# Fixed strategy priority as defined in requirements
class StrategyPriority:
    """Strategy priority ordering (highest to lowest)."""

    EXPANSION_FOLLOW = 1
    PULLBACK = 2
    TREND_CONTINUATION = 3
