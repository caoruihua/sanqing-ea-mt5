"""基于服务器日的日内盈利锁定控制器。"""

from dataclasses import dataclass
from datetime import datetime

from src.domain.constants import DEFAULT_DAILY_PROFIT_STOP_USD
from src.domain.models import RuntimeState


@dataclass
class DailyRiskUpdate:
    """一次日风险同步周期的结果。"""

    day_key: str
    daily_locked: bool
    daily_closed_profit: float
    reset_applied: bool


class DailyRiskController:
    """根据已实现平仓盈亏维护服务器日锁定状态。"""

    def __init__(self, daily_profit_stop_usd: float = DEFAULT_DAILY_PROFIT_STOP_USD) -> None:
        self.daily_profit_stop_usd = daily_profit_stop_usd

    def update(
        self,
        server_time: datetime,
        state: RuntimeState,
        daily_closed_profit: float,
    ) -> DailyRiskUpdate:
        day_key = server_time.strftime("%Y.%m.%d")
        reset_applied = False

        if state.day_key != day_key:
            state.day_key = day_key
            state.daily_locked = False
            state.daily_closed_profit = 0.0
            state.trades_today = 0
            reset_applied = True

        state.daily_closed_profit = daily_closed_profit
        if state.daily_closed_profit >= self.daily_profit_stop_usd:
            state.daily_locked = True

        return DailyRiskUpdate(
            day_key=state.day_key,
            daily_locked=state.daily_locked,
            daily_closed_profit=state.daily_closed_profit,
            reset_applied=reset_applied,
        )
