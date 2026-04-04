"""两阶段 ATR 仓位保护引擎。"""

from dataclasses import dataclass
from typing import Optional

from src.domain.constants import (
    PROTECTION_STAGE1_ATR_MULTIPLIER,
    PROTECTION_STAGE1_SL_BUFFER_ATR,
    PROTECTION_STAGE1_TP_ATR,
    PROTECTION_STAGE2_ATR_MULTIPLIER,
    PROTECTION_STAGE2_SL_DISTANCE_ATR,
    PROTECTION_STAGE2_TP_DISTANCE_ATR,
)
from src.domain.models import MarketSnapshot, OrderType, ProtectionStage, RuntimeState


@dataclass
class ProtectionDecision:
    """仓位保护更新的决策结果。"""

    action: str  # 保持 | 修改
    new_sl: Optional[float] = None
    new_tp: Optional[float] = None


class ProtectionEngine:
    """将保护状态从 NONE 推进到 STAGE1、再到 STAGE2，且不允许回退。"""

    def evaluate(
        self,
        order_type: OrderType,
        snapshot: MarketSnapshot,
        state: RuntimeState,
        current_sl: float,
        current_tp: float,
    ) -> ProtectionDecision:
        ps = state.protection_state
        if ps.entry_price is None or ps.entry_atr is None or ps.entry_atr <= 0:
            return ProtectionDecision(action="hold")

        entry = ps.entry_price
        atr = ps.entry_atr

        ps.highest_close_since_entry = max(
            ps.highest_close_since_entry or snapshot.close, snapshot.close
        )
        ps.lowest_close_since_entry = min(
            ps.lowest_close_since_entry or snapshot.close, snapshot.close
        )

        pnl_distance = self._profit_distance(order_type, snapshot.close, entry)

        if (
            ps.protection_stage == ProtectionStage.NONE
            and pnl_distance >= PROTECTION_STAGE1_ATR_MULTIPLIER * atr
        ):
            ps.protection_stage = ProtectionStage.STAGE1
            ps.stage1_activated_at = snapshot.last_closed_bar_time
            sl, tp = self._stage1_levels(order_type, entry, atr)
            return ProtectionDecision(
                action="modify",
                new_sl=sl,
                new_tp=max(tp, current_tp) if order_type == OrderType.BUY else min(tp, current_tp),
            )

        if pnl_distance >= PROTECTION_STAGE2_ATR_MULTIPLIER * atr:
            ps.protection_stage = ProtectionStage.STAGE2
            ps.trailing_active = True
            if ps.stage2_activated_at is None:
                ps.stage2_activated_at = snapshot.last_closed_bar_time

            sl, tp = self._stage2_levels(order_type, snapshot.close, atr)
            if order_type == OrderType.BUY:
                sl = max(current_sl, sl)
                tp = max(current_tp, tp)
            else:
                sl = min(current_sl, sl)
                tp = min(current_tp, tp)
            return ProtectionDecision(action="modify", new_sl=sl, new_tp=tp)

        return ProtectionDecision(action="hold")

    @staticmethod
    def _profit_distance(order_type: OrderType, close_price: float, entry_price: float) -> float:
        if order_type == OrderType.BUY:
            return close_price - entry_price
        return entry_price - close_price

    @staticmethod
    def _stage1_levels(order_type: OrderType, entry_price: float, entry_atr: float) -> tuple:
        if order_type == OrderType.BUY:
            return (
                entry_price + PROTECTION_STAGE1_SL_BUFFER_ATR * entry_atr,
                entry_price + PROTECTION_STAGE1_TP_ATR * entry_atr,
            )
        return (
            entry_price - PROTECTION_STAGE1_SL_BUFFER_ATR * entry_atr,
            entry_price - PROTECTION_STAGE1_TP_ATR * entry_atr,
        )

    @staticmethod
    def _stage2_levels(order_type: OrderType, close_price: float, entry_atr: float) -> tuple:
        if order_type == OrderType.BUY:
            return (
                close_price - PROTECTION_STAGE2_SL_DISTANCE_ATR * entry_atr,
                close_price + PROTECTION_STAGE2_TP_DISTANCE_ATR * entry_atr,
            )
        return (
            close_price + PROTECTION_STAGE2_SL_DISTANCE_ATR * entry_atr,
            close_price - PROTECTION_STAGE2_TP_DISTANCE_ATR * entry_atr,
        )
