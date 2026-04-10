import json
import urllib.error
import urllib.request

import pytest

from src.app.tick_http_ingress import TickHttpIngress


def _post_json(port: int, payload: dict) -> tuple[int, dict, str]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/tick",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, dict(response.headers), response.read().decode("utf-8")


def test_tick_http_ingress_returns_mt_compatible_success_payload():
    ingress = TickHttpIngress(symbol="XAUUSD", port=0)
    ingress.start()
    try:
        status, headers, body = _post_json(
            ingress.port,
            {
                "symbol": "XAUUSD",
                "closed_bar_time": 1712730000,
                "time_msc": 1712730000123,
                "bid": 2333.1,
                "ask": 2333.3,
                "sequence": 1,
            },
        )
        payload = json.loads(body)

        assert status == 200
        assert headers["Content-Type"] == "application/json; charset=utf-8"
        assert payload == {
            "accepted": True,
            "ok": True,
            "status": 0,
            "code": 0,
            "message": "accepted",
        }
        assert ingress.wait().sequence == 1
    finally:
        ingress.stop()


def test_tick_http_ingress_marks_duplicate_payload_as_replayed():
    ingress = TickHttpIngress(symbol="XAUUSD", port=0)
    ingress.start()
    payload = {
        "symbol": "XAUUSD",
        "closed_bar_time": 1712730000,
        "time_msc": 1712730000123,
        "bid": 2333.1,
        "ask": 2333.3,
        "sequence": 1,
    }
    try:
        _post_json(ingress.port, payload)
        status, _, body = _post_json(ingress.port, payload)
        response_payload = json.loads(body)

        assert status == 200
        assert response_payload["accepted"] is True
        assert response_payload["replayed"] is True
        assert response_payload["status"] == 0
    finally:
        ingress.stop()


def test_tick_http_ingress_rejects_out_of_order_sequence():
    ingress = TickHttpIngress(symbol="XAUUSD", port=0)
    ingress.start()
    try:
        _post_json(
            ingress.port,
            {
                "symbol": "XAUUSD",
                "closed_bar_time": 1712730000,
                "time_msc": 1712730000123,
                "bid": 2333.1,
                "ask": 2333.3,
                "sequence": 2,
            },
        )

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _post_json(
                ingress.port,
                {
                    "symbol": "XAUUSD",
                    "closed_bar_time": 1712730000,
                    "time_msc": 1712730000123,
                    "bid": 2333.1,
                    "ask": 2333.3,
                    "sequence": 1,
                },
            )

        assert exc_info.value.code == 409
    finally:
        ingress.stop()
