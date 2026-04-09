"""
该文件负责实现入场门控流水线，在真正发单前逐条校验是否允许开仓。

主要职责：
1. 拦截重复 bar 的重复入场；
2. 拦截日锁盈、超日交易次数、已有持仓等风险条件；
3. 执行低波动过滤；
4. 在所有门控通过后生成 `TradeIntent` 给执行引擎。

说明：
- 本文件只做"允许/不允许"的判断；
- 不直接向 MT5 发送交易请求；
- 所有拦截都返回稳定 reason code，便于日志和测试。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4

from src.domain.constants import (
    DEFAULT_LOW_VOL_ATR_POINTS_FLOOR,
    DEFAULT_LOW_VOL_ATR_SPREAD_RATIO_FLOOR,
    DEFAULT_MAX_TRADES_PER_DAY,
    DEFAULT_TRADING_BLACKOUT_PERIODS,
    RejectionReason,
)
from src.domain.models import MarketSnapshot, RuntimeState, SignalDecision, TradeIntent
from src.utils.logger import StructuredLogger


@dataclass
class EntryGateResult:
    """单次收盘 K 线入场尝试的门控结果。"""

    intent: Optional[TradeIntent]
    reason_code: Optional[str]


class EntryGate:
    """在创建 `TradeIntent` 前按固定顺序执行门控检查。"""

    def __init__(
        self,
        max_trades_per_day: int = DEFAULT_MAX_TRADES_PER_DAY,
        low_vol_atr_points_floor: float = DEFAULT_LOW_VOL_ATR_POINTS_FLOOR,
        low_vol_atr_spread_ratio_floor: float = DEFAULT_LOW_VOL_ATR_SPREAD_RATIO_FLOOR,
        trading_blackout_periods: Optional[list] = None,
        logger: Optional[StructuredLogger] = None,
    ) -> None:
        self.max_trades_per_day = max_trades_per_day
        self.low_vol_atr_points_floor = low_vol_atr_points_floor
        self.low_vol_atr_spread_ratio_floor = low_vol_atr_spread_ratio_floor
        self.trading_blackout_periods = trading_blackout_periods or DEFAULT_TRADING_BLACKOUT_PERIODS
        self.logger = logger
        self._was_in_blackout = True  # 初始化时假设在禁止时段，启动时会自动检测

    def evaluate(
        self,
        signal: SignalDecision,
        snapshot: MarketSnapshot,
        state: RuntimeState,
        has_existing_position: bool,
        strategy_can_trade: bool,
        action_id: Optional[str] = None,
    ) -> EntryGateResult:
        """按严格顺序执行入场检查，并在通过时返回 `TradeIntent`。"""
        strategy_name = signal.strategy_name

        if state.last_entry_bar_time == snapshot.last_closed_bar_time:
            reason = RejectionReason.NOT_NEW_CLOSED_BAR
            self._log_rejection(strategy_name, reason, snapshot.symbol)
            return EntryGateResult(intent=None, reason_code=reason)

        current_time = snapshot.last_closed_bar_time
        is_in_blackout = self._is_in_blackout_period(current_time)
        
        # 检测时间段切换：从禁止时段切换到交易时段
        if self._was_in_blackout and not is_in_blackout:
            self._log_trading_resumed(current_time)
        
        self._was_in_blackout = is_in_blackout
        
        if is_in_blackout:
            reason = RejectionReason.TRADING_BLACKOUT
            self._log_rejection(strategy_name, reason, snapshot.symbol)
            return EntryGateResult(intent=None, reason_code=reason)

        if state.daily_locked:
            reason = RejectionReason.DAILY_LOCKED
            self._log_rejection(strategy_name, reason, snapshot.symbol)
            return EntryGateResult(intent=None, reason_code=reason)

        if state.trades_today >= self.max_trades_per_day:
            reason = RejectionReason.MAX_TRADES_EXCEEDED
            self._log_rejection(strategy_name, reason, snapshot.symbol)
            return EntryGateResult(intent=None, reason_code=reason)

        if has_existing_position:
            reason = RejectionReason.EXISTING_POSITION
            self._log_rejection(strategy_name, reason, snapshot.symbol)
            return EntryGateResult(intent=None, reason_code=reason)

        if self._is_low_volatility(snapshot):
            reason = RejectionReason.LOW_VOLATILITY
            self._log_rejection(strategy_name, reason, snapshot.symbol)
            return EntryGateResult(intent=None, reason_code=reason)

        if not strategy_can_trade:
            reason = RejectionReason.STRATEGY_CANNOT_TRADE
            self._log_rejection(strategy_name, reason, snapshot.symbol)
            return EntryGateResult(intent=None, reason_code=reason)

        resolved_action_id = action_id or self._make_action_id(snapshot, signal)
        intent = TradeIntent(
            signal_decision=signal,
            market_snapshot=snapshot,
            action_id=resolved_action_id,
        )
        state.last_entry_bar_time = snapshot.last_closed_bar_time
        return EntryGateResult(intent=intent, reason_code=None)

    def _log_rejection(self, strategy_name: str, reason: str, symbol: str) -> None:
        """记录门控拒绝日志。"""
        if self.logger is not None:
            event_name = f"{strategy_name}_entry_rejected"
            self.logger.warning(
                event_name,
                strategy_name=strategy_name,
                reason=reason,
                symbol=symbol,
            )

    def _log_trading_resumed(self, dt: datetime) -> None:
        """记录从禁止时段切换到交易时段的日志。"""
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        if self.logger is not None:
            self.logger.info(
                "trading_period_resumed",
                timestamp=time_str,
                message=f"交易时段已恢复，当前时间 {time_str}，可以开仓",
            )
        else:
            print(f"[INFO] 交易时段已恢复，当前时间 {time_str}，可以开仓")

    def _is_low_volatility(self, snapshot: MarketSnapshot) -> bool:
        atr_points = snapshot.atr14 * (10**snapshot.digits)
        if atr_points < self.low_vol_atr_points_floor:
            return True

        if snapshot.spread_points <= 0:
            return True

        atr_spread_ratio = atr_points / snapshot.spread_points
        return atr_spread_ratio < self.low_vol_atr_spread_ratio_floor

    def _is_in_blackout_period(self, dt: datetime) -> bool:
        """检查当前时间是否在禁止开仓时间段内。"""
        current_hour = dt.hour + dt.minute / 60.0
        for start_hour, end_hour in self.trading_blackout_periods:
            if start_hour <= end_hour:
                # 正常时间段，如 (1.0, 7.0) 表示 01:00-07:00
                if start_hour <= current_hour < end_hour:
                    return True
            else:
                # 跨午夜的时间段，如 (22.0, 6.0) 表示 22:00-06:00
                if current_hour >= start_hour or current_hour < end_hour:
                    return True
        return False

    @staticmethod
    def _make_action_id(snapshot: MarketSnapshot, signal: SignalDecision) -> str:
        bar_key = snapshot.last_closed_bar_time.strftime("%Y%m%d%H%M")
        return f"{signal.strategy_name}-{bar_key}-{uuid4().hex[:8]}"