"""Integration tests for SimBrokerAdapter."""

from datetime import datetime

from src.adapters.sim_broker import SimBrokerAdapter


def test_order_lifecycle() -> None:
    broker = SimBrokerAdapter()
    assert broker.connect() is True

    order_result = broker.send_order(
        symbol="XAUUSD",
        magic=20260313,
        order_type="BUY",
        volume=0.01,
        price=2350.0,
        sl=2340.0,
        tp=2370.0,
        slippage=30,
        comment="test-order",
    )
    assert order_result["success"] is True
    ticket = order_result["ticket"]

    position = broker.get_position(symbol="XAUUSD", magic=20260313)
    assert position is not None
    assert position["ticket"] == ticket

    modify_result = broker.modify_position(ticket=ticket, sl=2345.0, tp=2375.0)
    assert modify_result["success"] is True

    close_result = broker.close_position(
        ticket=ticket,
        close_price=2360.0,
        closed_at=datetime(2026, 4, 3, 10, 10, 0),
    )
    assert close_result["success"] is True

    position_after = broker.get_position(symbol="XAUUSD", magic=20260313)
    assert position_after is None

    assert broker.get_closed_profit(day_key="2026.04.03") > 0
