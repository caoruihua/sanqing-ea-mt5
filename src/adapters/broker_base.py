"""
该文件定义 Broker 适配器的抽象接口，用于统一 MT5 真实连接和模拟回测的实现。

主要职责：
1. 定义所有 Broker 适配器必须实现的统一接口；
2. 屏蔽底层 Broker 差异，让核心流程可以无差别调用；
3. 支持 MT5 真实账户和模拟回测两种后端。

说明：
- 该文件只定义接口，不包含具体实现；
- 具体实现由 MT5BrokerAdapter 和 SimBrokerAdapter 提供。
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional


class BrokerAdapter(ABC):
    """核心执行/编排模块使用的统一 Broker 接口。"""

    @abstractmethod
    def connect(self) -> bool:
        """初始化 Broker 连接。"""

    @abstractmethod
    def get_rates(self, symbol: str, timeframe: int, count: int) -> List[Dict[str, Any]]:
        """获取最近 K 线数据，最新数据在最后。"""

    @abstractmethod
    def get_position(self, symbol: str, magic: int) -> Optional[Dict[str, Any]]:
        """获取指定 symbol+magic 的当前持仓，若无持仓则返回 None。"""

    @abstractmethod
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
        """提交市价单请求。"""

    @abstractmethod
    def modify_position(self, ticket: int, sl: float, tp: float) -> Dict[str, Any]:
        """修改活跃持仓的止损/止盈价位。"""

    @abstractmethod
    def close_position(
        self, ticket: int, close_price: float, closed_at: datetime
    ) -> Dict[str, Any]:
        """平仓并返回平仓结果。"""

    @abstractmethod
    def get_closed_profit(self, day_key: str) -> float:
        """获取指定服务器日的已实现平仓盈亏。"""
