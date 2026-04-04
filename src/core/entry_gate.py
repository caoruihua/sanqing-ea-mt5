"""
该文件负责实现入场门控流水线，在真正发单前逐条校验是否允许开仓。

主要职责：
1. 拦截重复 bar 的重复入场；
2. 拦截日锁盈、超日交易次数、已有持仓等风险条件；
3. 执行低波动过滤；
4. 在所有门控通过后生成 `TradeIntent` 给执行引擎。

说明：
- 本文件只做“允许/不允许”的判断；
- 不直接向 MT5 发送交易请求；
- 所有拦截都返回稳定 reason code，便于日志和测试。
"""

from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from src.domain.constants import (
    DEFAULT_LOW_VOL_ATR_POINTS_FLOOR,
    DEFAULT_LOW_VOL_ATR_SPREAD_RATIO_FLOOR,
    DEFAULT_MAX_TRADES_PER_DAY,
    RejectionReason,
)
from src.domain.models import MarketSnapshot, RuntimeState, SignalDecision, TradeIntent


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
    ) -> None:
        self.max_trades_per_day = max_trades_per_day
        self.low_vol_atr_points_floor = low_vol_atr_points_floor
        self.low_vol_atr_spread_ratio_floor = low_vol_atr_spread_ratio_floor

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
        if state.last_entry_bar_time == snapshot.last_closed_bar_time:
            return EntryGateResult(intent=None, reason_code=RejectionReason.NOT_NEW_CLOSED_BAR)

        if state.daily_locked:
            return EntryGateResult(intent=None, reason_code=RejectionReason.DAILY_LOCKED)

        if state.trades_today >= self.max_trades_per_day:
            return EntryGateResult(intent=None, reason_code=RejectionReason.MAX_TRADES_EXCEEDED)

        if has_existing_position:
            return EntryGateResult(intent=None, reason_code=RejectionReason.EXISTING_POSITION)

        if self._is_low_volatility(snapshot):
            return EntryGateResult(intent=None, reason_code=RejectionReason.LOW_VOLATILITY)

        if not strategy_can_trade:
            return EntryGateResult(intent=None, reason_code=RejectionReason.STRATEGY_CANNOT_TRADE)

        resolved_action_id = action_id or self._make_action_id(snapshot, signal)
        intent = TradeIntent(
            signal_decision=signal,
            market_snapshot=snapshot,
            action_id=resolved_action_id,
        )
        state.last_entry_bar_time = snapshot.last_closed_bar_time
        return EntryGateResult(intent=intent, reason_code=None)

    def _is_low_volatility(self, snapshot: MarketSnapshot) -> bool:
        atr_points = snapshot.atr14 * (10**snapshot.digits)
        if atr_points < self.low_vol_atr_points_floor:
            return True

        if snapshot.spread_points <= 0:
            return True

        atr_spread_ratio = atr_points / snapshot.spread_points
        return atr_spread_ratio < self.low_vol_atr_spread_ratio_floor

    @staticmethod
    def _make_action_id(snapshot: MarketSnapshot, signal: SignalDecision) -> str:
        bar_key = snapshot.last_closed_bar_time.strftime("%Y%m%d%H%M")
        return f"{signal.strategy_name}-{bar_key}-{uuid4().hex[:8]}"
