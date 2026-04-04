"""
该文件提供用于测试和模拟模式的确定性内存中 Broker 实现。

主要职责：
1. 在内存中模拟持仓、订单和盈亏状态；
2. 支持测试时预设 K 线数据，实现确定性回放；
3. 提供与 MT5BrokerAdapter 相同的接口，方便测试替换。

说明：
- 该适配器不连接真实 MT5；
- 所有数据保存在内存中，进程结束后数据丢失；
- 适用于单元测试和策略回测。
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.adapters.broker_base import BrokerAdapter


class SimBrokerAdapter(BrokerAdapter):
    """内存中的单持仓 Broker，行为确定性，用于测试。"""

    def __init__(self) -> None:
        self.connected = False
        self._next_ticket = 1
        self._positions_by_ticket: Dict[int, Dict[str, Any]] = {}
        self._position_key_to_ticket: Dict[str, int] = {}
        self._closed_profit_by_day: Dict[str, float] = {}
        self._rates: Dict[str, List[Dict[str, Any]]] = {}

    def connect(self) -> bool:
        self.connected = True
        return True

    def get_rates(self, symbol: str, timeframe: int, count: int) -> List[Dict[str, Any]]:
        _ = timeframe
        rates = self._rates.get(symbol, [])
        if count <= 0:
            return []
        return rates[-count:]

    def seed_rates(self, symbol: str, rates: List[Dict[str, Any]]) -> None:
        """供测试使用的辅助函数，用于注入可重复回放的行情数据。"""
        self._rates[symbol] = list(rates)

    def get_position(self, symbol: str, magic: int) -> Optional[Dict[str, Any]]:
        ticket = self._position_key_to_ticket.get(self._position_key(symbol, magic))
        if ticket is None:
            return None
        return self._positions_by_ticket.get(ticket)

    def send_order(
        self,
        symbol: str,
        magic: int,
        order_type: str,
        volume: float,
        price: float,
        sl: float,
        tp: float,
        slippage: int,
        comment: str,
    ) -> Dict[str, Any]:
        _ = slippage
        key = self._position_key(symbol, magic)
        if key in self._position_key_to_ticket:
            return {"success": False, "retcode": 10013, "reason": "EXISTING_POSITION"}

        ticket = self._next_ticket
        self._next_ticket += 1
        position = {
            "ticket": ticket,
            "symbol": symbol,
            "magic": magic,
            "order_type": order_type,
            "volume": volume,
            "entry_price": price,
            "sl": sl,
            "tp": tp,
            "comment": comment,
            "opened_at": datetime.now(timezone.utc),
        }
        self._positions_by_ticket[ticket] = position
        self._position_key_to_ticket[key] = ticket
        return {"success": True, "retcode": 10009, "ticket": ticket}

    def modify_position(self, ticket: int, sl: float, tp: float) -> Dict[str, Any]:
        position = self._positions_by_ticket.get(ticket)
        if position is None:
            return {"success": False, "retcode": 10036, "reason": "POSITION_NOT_FOUND"}
        position["sl"] = sl
        position["tp"] = tp
        return {"success": True, "retcode": 10009}

    def close_position(
        self, ticket: int, close_price: float, closed_at: datetime
    ) -> Dict[str, Any]:
        position = self._positions_by_ticket.get(ticket)
        if position is None:
            return {"success": False, "retcode": 10036, "reason": "POSITION_NOT_FOUND"}

        direction = 1.0 if position["order_type"] == "BUY" else -1.0
        points = (close_price - position["entry_price"]) * direction
        profit = points * position["volume"] * 100.0

        day_key = closed_at.strftime("%Y.%m.%d")
        self._closed_profit_by_day[day_key] = self._closed_profit_by_day.get(day_key, 0.0) + profit

        key = self._position_key(position["symbol"], position["magic"])
        del self._positions_by_ticket[ticket]
        del self._position_key_to_ticket[key]
        return {"success": True, "retcode": 10009, "profit": profit}

    def get_closed_profit(self, day_key: str) -> float:
        return self._closed_profit_by_day.get(day_key, 0.0)

    @staticmethod
    def _position_key(symbol: str, magic: int) -> str:
        return f"{symbol}:{magic}"
