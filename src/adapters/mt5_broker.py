"""
该文件负责封装 MetaTrader5 官方 Python 库，向本机已经打开并登录的 MT5 终端发送指令。

主要职责：
1. 建立 Python 与本机 MT5 终端之间的连接；
2. 获取 K 线、持仓、历史成交等交易数据；
3. 发送下单、改单、平仓请求；
4. 把 MT5 原始 retcode 统一转换成项目内部更易处理的结果结构。

注意事项：
- 本文件不负责登录 MT5 账户；
- 不负责区分模拟盘/实盘；
- 默认要求用户已经手动把本机 MT5 终端配置并登录好。
"""

import importlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.adapters.broker_base import BrokerAdapter

try:  # pragma: no cover - import availability is environment-dependent
    _mt5 = importlib.import_module("MetaTrader5")
except Exception:  # pragma: no cover - keep adapter importable without MT5 terminal
    _mt5 = None

mt5: Any = _mt5


class UnknownRetcodeError(ValueError):
    """Raised when retcode has no mapping in normalized table."""


class MT5ConnectionError(RuntimeError):
    """Raised when Python cannot initialize a connection to local MT5 terminal."""


@dataclass(frozen=True)
class RetcodeMapping:
    """Normalized retcode semantics for retry/success decisions."""

    code: int
    reason: str
    success: bool
    retryable: bool


_RETCODE_TABLE = {
    10004: RetcodeMapping(10004, "REQUOTE", success=False, retryable=True),
    10006: RetcodeMapping(10006, "REJECT", success=False, retryable=False),
    10008: RetcodeMapping(10008, "PLACED", success=True, retryable=False),
    10009: RetcodeMapping(10009, "DONE", success=True, retryable=False),
    10010: RetcodeMapping(10010, "DONE_PARTIAL", success=True, retryable=False),
    10012: RetcodeMapping(10012, "TIMEOUT", success=False, retryable=True),
    10013: RetcodeMapping(10013, "INVALID_REQUEST", success=False, retryable=False),
    10014: RetcodeMapping(10014, "INVALID_VOLUME", success=False, retryable=False),
    10017: RetcodeMapping(10017, "TRADE_DISABLED", success=False, retryable=False),
    10018: RetcodeMapping(10018, "MARKET_CLOSED", success=False, retryable=False),
    10019: RetcodeMapping(10019, "NO_MONEY", success=False, retryable=False),
    10020: RetcodeMapping(10020, "PRICE_CHANGED", success=False, retryable=True),
    10021: RetcodeMapping(10021, "PRICE_OFF", success=False, retryable=True),
    10024: RetcodeMapping(10024, "TOO_MANY_REQUESTS", success=False, retryable=True),
    10025: RetcodeMapping(10025, "NO_CHANGES", success=True, retryable=False),
    10026: RetcodeMapping(10026, "SERVER_DISABLES_AT", success=False, retryable=False),
    10027: RetcodeMapping(10027, "CLIENT_DISABLES_AT", success=False, retryable=False),
    10028: RetcodeMapping(10028, "LOCKED", success=False, retryable=True),
    10029: RetcodeMapping(10029, "FROZEN", success=False, retryable=False),
    10031: RetcodeMapping(10031, "CONNECTION", success=False, retryable=True),
    10036: RetcodeMapping(10036, "POSITION_CLOSED", success=False, retryable=False),
}


def normalize_retcode(retcode: int) -> RetcodeMapping:
    """Convert raw MT5 retcode to normalized semantics."""
    if retcode not in _RETCODE_TABLE:
        raise UnknownRetcodeError(f"Unknown MT5 retcode: {retcode}")
    return _RETCODE_TABLE[retcode]


class MT5BrokerAdapter(BrokerAdapter):
    """对 MT5 官方库做最薄的一层封装，供策略执行链路统一调用。"""

    def __init__(self) -> None:
        self.last_connect_error: Optional[str] = None

    def connect(self) -> bool:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is unavailable")
        connected = bool(mt5.initialize())
        if connected:
            self.last_connect_error = None
            return True

        error_code, error_message = mt5.last_error()
        self.last_connect_error = (
            f"MT5 initialize failed: code={error_code}, message={error_message}"
        )
        return False

    def get_rates(self, symbol: str, timeframe: int, count: int) -> List[Dict[str, Any]]:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is unavailable")
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 1, count)
        if rates is None:
            return []
        field_names = list(getattr(rates.dtype, "names", []) or [])
        normalized = [dict(zip(field_names, row.tolist())) for row in rates]
        normalized.sort(key=lambda item: int(item.get("time", 0)))
        return normalized

    def get_position(self, symbol: str, magic: int) -> Optional[Dict[str, Any]]:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is unavailable")
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return None
        for pos in positions:
            as_dict = pos._asdict()
            if int(as_dict.get("magic", -1)) == magic:
                return as_dict
        return None

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
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is unavailable")

        mt5_order_type = mt5.ORDER_TYPE_BUY if order_type == "BUY" else mt5.ORDER_TYPE_SELL
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "magic": magic,
            "type": mt5_order_type,
            "volume": volume,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": slippage,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None:
            return {"success": False, "reason": "NO_RESULT", "retryable": True}

        mapped = normalize_retcode(int(result.retcode))
        return {
            "success": mapped.success,
            "retcode": mapped.code,
            "reason": mapped.reason,
            "retryable": mapped.retryable,
            "ticket": int(getattr(result, "order", 0)),
            "raw": result,
        }

    def modify_position(self, ticket: int, sl: float, tp: float) -> Dict[str, Any]:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is unavailable")
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": sl,
            "tp": tp,
        }
        result = mt5.order_send(request)
        if result is None:
            return {"success": False, "reason": "NO_RESULT", "retryable": True}
        mapped = normalize_retcode(int(result.retcode))
        return {
            "success": mapped.success,
            "retcode": mapped.code,
            "reason": mapped.reason,
            "retryable": mapped.retryable,
            "raw": result,
        }

    def close_position(
        self, ticket: int, close_price: float, closed_at: datetime
    ) -> Dict[str, Any]:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is unavailable")

        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return {"success": False, "reason": "POSITION_NOT_FOUND", "retryable": False}

        pos = positions[0]
        pos_type = int(pos.type)
        close_type = mt5.ORDER_TYPE_SELL if pos_type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "position": int(pos.ticket),
            "type": close_type,
            "volume": float(pos.volume),
            "price": close_price,
            "deviation": 30,
            "comment": f"close@{closed_at.isoformat()}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None:
            return {"success": False, "reason": "NO_RESULT", "retryable": True}

        mapped = normalize_retcode(int(result.retcode))
        return {
            "success": mapped.success,
            "retcode": mapped.code,
            "reason": mapped.reason,
            "retryable": mapped.retryable,
            "ticket": int(getattr(result, "order", ticket)),
            "raw": result,
        }

    def get_closed_profit(self, day_key: str) -> float:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is unavailable")

        day_start = datetime.strptime(day_key, "%Y.%m.%d")
        day_end = day_start + timedelta(days=1)
        deals = mt5.history_deals_get(day_start, day_end)
        if not deals:
            return 0.0

        total_profit = 0.0
        out_entry = getattr(mt5, "DEAL_ENTRY_OUT", -2)
        out_by_entry = getattr(mt5, "DEAL_ENTRY_OUT_BY", -3)
        for deal in deals:
            entry = int(getattr(deal, "entry", -1))
            if entry not in {out_entry, out_by_entry}:
                continue
            total_profit += float(getattr(deal, "profit", 0.0))
            total_profit += float(getattr(deal, "swap", 0.0))
            total_profit += float(getattr(deal, "commission", 0.0))
            total_profit += float(getattr(deal, "fee", 0.0))

        return total_profit
