"""
该文件是项目的主运行入口，负责连接本机已经登录好的 MT5 终端并执行策略分析/发单流程。

主要职责：
1. 读取本地配置；
2. 连接本机 MT5 终端；
3. 拉取最新报价与已收盘 K 线；
4. 构建市场快照并交给编排器处理；
5. 持续轮询，按收盘 K 语义完成策略分析与下单。

注意事项：
- 本文件不负责登录 MT5；
- 不区分模拟盘/实盘；
- 默认要求用户已经手动打开并登录本机 MT5。
"""

import argparse
import configparser
import importlib
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, TextIO

from src.adapters.mt5_broker import MT5BrokerAdapter
from src.app.poll_ingress import PollIngress
from src.app.run_config import TriggerConfig, TriggerMode
from src.app.tick_http_ingress import TickHttpIngress
from src.app.tick_ingress import TickWakeupPayload
from src.core.context_builder import ContextBuilder, InsufficientBarsError
from src.core.entry_gate import EntryGate
from src.core.strategy_selector import StrategySelector
from src.domain.constants import DEFAULT_FIXED_LOTS, DEFAULT_MAGIC_NUMBER, DEFAULT_MAX_RETRIES
from src.domain.models import MarketSnapshot, RuntimeState

# 控制台文件日志管理器
class ConsoleFileLogger:
    """按小时保存控制台日志到文件。"""

    def __init__(self, log_dir: str = "logs/console") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._current_file: Optional[TextIO] = None
        self._current_hour: Optional[str] = None
        self._lock = threading.Lock()

    def _get_current_hour(self) -> str:
        """获取当前小时字符串（用于文件名）。"""
        return datetime.now().strftime("%Y-%m-%d_%H")

    def _get_log_path(self, hour_str: str) -> Path:
        """获取指定小时的日志文件路径。"""
        return self.log_dir / f"console_{hour_str}.log"

    def _open_new_file(self, hour_str: str) -> None:
        """打开新的日志文件。"""
        if self._current_file is not None:
            self._current_file.close()

        log_path = self._get_log_path(hour_str)
        self._current_file = open(log_path, "a", encoding="utf-8", buffering=1)
        self._current_hour = hour_str

        # 写入文件头
        header = f"\n{'='*60}\n"
        header += f"# 控制台日志开始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"{'='*60}\n"
        self._current_file.write(header)
        self._current_file.flush()

    def write(self, message: str) -> None:
        """写入日志消息（自动按小时切换文件）。"""
        with self._lock:
            current_hour = self._get_current_hour()

            # 如果小时变化，创建新文件
            if current_hour != self._current_hour:
                self._open_new_file(current_hour)

            # 写入消息
            if self._current_file is not None:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._current_file.write(f"[{timestamp}] {message}\n")
                self._current_file.flush()

    def close(self) -> None:
        """关闭日志文件。"""
        with self._lock:
            if self._current_file is not None:
                self._current_file.close()
                self._current_file = None


# 控制台文件日志实例
_console_file_logger: Optional[ConsoleFileLogger] = None

# 控制台状态（每30秒打印一次最新的tick和策略结果）
_console_lock = threading.Lock()
_console_timer: threading.Timer | None = None
_CONSOLE_FLUSH_INTERVAL = 10.0  # 10秒刷新一次

# 存储最新的状态
_latest_runtime_status: Optional[str] = None
_latest_tick_info: Optional[str] = None
_latest_strategy_result: Optional[str] = None


def _start_console_timer() -> None:
    """启动控制台定时刷新定时器。"""
    global _console_timer
    _console_timer = threading.Timer(_CONSOLE_FLUSH_INTERVAL, _scheduled_console_flush)
    _console_timer.daemon = True
    _console_timer.start()


def _scheduled_console_flush() -> None:
    """定时器触发的控制台刷新。"""
    _flush_console()
    _start_console_timer()


def _flush_console() -> None:
    """将最新的tick和策略结果输出到控制台，并写入文件。"""
    global _latest_runtime_status, _latest_tick_info, _latest_strategy_result
    with _console_lock:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines_to_write = []

        if _latest_runtime_status is not None:
            line = f"[{now}] [STATUS] {_latest_runtime_status}"
            print(line)
            lines_to_write.append(line)
        if _latest_tick_info is not None:
            line = f"[{now}] [TICK] {_latest_tick_info}"
            print(line)
            lines_to_write.append(line)
        if _latest_strategy_result is not None:
            line = f"[{now}] [RESULT] {_latest_strategy_result}"
            print(line)
            lines_to_write.append(line)

        if lines_to_write:
            sys.stdout.flush()
            # 同时写入文件
            if _console_file_logger is not None:
                for line in lines_to_write:
                    _console_file_logger.write(line)


_orchestrator = importlib.import_module("src.app.orchestrator")
_daily_risk_controller = importlib.import_module("src.core.daily_risk_controller")
_execution_engine = importlib.import_module("src.core.execution_engine")
_protection_engine = importlib.import_module("src.core.protection_engine")
_state_store = importlib.import_module("src.core.state_store")
_logger = importlib.import_module("src.utils.logger")

Orchestrator = _orchestrator.Orchestrator
DailyRiskController = _daily_risk_controller.DailyRiskController
ExecutionEngine = _execution_engine.ExecutionEngine
ProtectionEngine = _protection_engine.ProtectionEngine
StateStore = _state_store.StateStore
StructuredLogger = _logger.StructuredLogger


def _update_tick_info(message: str) -> None:
    """更新最新的tick报价信息（每30秒打印一次）。"""
    global _latest_tick_info
    with _console_lock:
        _latest_tick_info = message


def _update_strategy_result(message: str) -> None:
    """更新最新的策略处理结果（每30秒打印一次）。"""
    global _latest_strategy_result
    with _console_lock:
        _latest_strategy_result = message


def _console_status(message: str) -> None:
    """更新控制台状态（每10秒统一打印一次）。"""
    global _latest_runtime_status
    with _console_lock:
        _latest_runtime_status = message


def _load_config(config_path: str) -> configparser.ConfigParser:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    return parser


def _resolve_timeframe(mt5_module, timeframe_minutes: int) -> int:
    """把分钟级时间框映射到 MT5 官方常量。"""
    mapping = {
        1: mt5_module.TIMEFRAME_M1,
        5: mt5_module.TIMEFRAME_M5,
        15: mt5_module.TIMEFRAME_M15,
        30: mt5_module.TIMEFRAME_M30,
        60: mt5_module.TIMEFRAME_H1,
        240: mt5_module.TIMEFRAME_H4,
        1440: mt5_module.TIMEFRAME_D1,
    }
    if timeframe_minutes not in mapping:
        raise ValueError(f"Unsupported timeframe minutes: {timeframe_minutes}")
    return mapping[timeframe_minutes]


def _rate_to_bar(rate: Dict[str, object]) -> tuple:
    """把 MT5 K 线字典转换成 ContextBuilder 需要的元组结构。"""
    rate_any: Dict[str, Any] = dict(rate)
    return (
        datetime.fromtimestamp(int(rate_any["time"])),
        float(rate_any["open"]),
        float(rate_any["high"]),
        float(rate_any["low"]),
        float(rate_any["close"]),
        int(rate_any.get("tick_volume", 0)),
        int(rate_any.get("spread", 0)),
        int(rate_any.get("real_volume", 0)),
    )


def _build_snapshot_from_mt5(
    broker: MT5BrokerAdapter,
    mt5_module,
    builder: ContextBuilder,
    symbol: str,
    timeframe_minutes: int,
    bars_count: int,
    wakeup_payload: Optional[TickWakeupPayload] = None,
) -> MarketSnapshot:
    """从本机 MT5 终端拉取数据并构建市场快照。"""
    timeframe = _resolve_timeframe(mt5_module, timeframe_minutes)
    if wakeup_payload is not None and hasattr(broker, "get_rates_until"):
        lookback_seconds = max((bars_count + 5) * timeframe_minutes * 60, timeframe_minutes * 60)
        rates = broker.get_rates_until(
            symbol=symbol,
            timeframe=timeframe,
            count=bars_count,
            end_time=wakeup_payload.closed_bar_time,
            lookback_seconds=lookback_seconds,
        )
    else:
        rates = broker.get_rates(symbol=symbol, timeframe=timeframe, count=bars_count)
    if not rates:
        raise ValueError(
            f"No MT5 rates available for symbol={symbol}, timeframe={timeframe_minutes}"
        )

    symbol_info = mt5_module.symbol_info(symbol)
    if symbol_info is None:
        raise ValueError(f"No symbol info available for symbol={symbol}")

    bars = [_rate_to_bar(rate) for rate in rates]
    if wakeup_payload is not None:
        expected_bar_time = datetime.fromtimestamp(wakeup_payload.closed_bar_time)
        latest_bar_time = bars[-1][0]
        if latest_bar_time != expected_bar_time:
            raise ValueError(
                "Wake-up payload bar mismatch: "
                f"expected={expected_bar_time.isoformat()}, actual={latest_bar_time.isoformat()}"
            )
        bid = float(wakeup_payload.bid)
        ask = float(wakeup_payload.ask)
    else:
        tick = mt5_module.symbol_info_tick(symbol)
        if tick is None:
            raise ValueError(f"No tick available for symbol={symbol}")
        bid = float(tick.bid)
        ask = float(tick.ask)
    builder.digits = int(symbol_info.digits)
    return builder.build_snapshot(bars=bars, bid=bid, ask=ask)


def _create_ingress(trigger_config: TriggerConfig, poll_sec: float, symbol: str):
    """Create the configured runtime ingress without silently changing trigger mode."""
    if trigger_config.trigger_mode == TriggerMode.POLL:
        return PollIngress(poll_interval_seconds=poll_sec, symbol=symbol)
    return TickHttpIngress(
        host=trigger_config.host,
        port=trigger_config.port,
        symbol=trigger_config.symbol,
        queue_policy=trigger_config.queue_policy,
    )


def _process_runtime_cycle(
    *,
    broker: MT5BrokerAdapter,
    mt5_module,
    builder: ContextBuilder,
    symbol: str,
    timeframe_minutes: int,
    bars_count: int,
    orchestrator: Orchestrator,
    logger: StructuredLogger,
    wakeup_payload: Optional[TickWakeupPayload] = None,
) -> None:
    """Build one snapshot from MT5 and hand it to the orchestrator."""
    _console_status("正在从 MT5 拉取最新报价与已收盘 K 线...")
    snapshot = _build_snapshot_from_mt5(
        broker=broker,
        mt5_module=mt5_module,
        builder=builder,
        symbol=symbol,
        timeframe_minutes=timeframe_minutes,
        bars_count=bars_count,
        wakeup_payload=wakeup_payload,
    )
    _console_status(
        f"快照构建完成: bar_time={snapshot.last_closed_bar_time}, bid={snapshot.bid}, ask={snapshot.ask}, ema_fast={snapshot.ema_fast:.5f}, ema_slow={snapshot.ema_slow:.5f}, atr14={snapshot.atr14:.5f}"
    )
    result = orchestrator.process_snapshot(snapshot)
    _update_strategy_result(
        f"success={result.get('success')}, reason={result.get('reason')}, exec_reason={((result.get('result') or {}).get('reason')) if isinstance(result.get('result'), dict) else None}, retcode={((result.get('result') or {}).get('retcode')) if isinstance(result.get('result'), dict) else None}, trace={result.get('trace')}"
    )


def _run_processing_cycle(
    *,
    broker: MT5BrokerAdapter,
    mt5_module,
    builder: ContextBuilder,
    symbol: str,
    timeframe_minutes: int,
    bars_count: int,
    orchestrator: Orchestrator,
    logger: StructuredLogger,
    wakeup_payload: Optional[TickWakeupPayload] = None,
) -> None:
    """Run one protected processing cycle, preserving runtime logging behavior."""
    try:
        _process_runtime_cycle(
            broker=broker,
            mt5_module=mt5_module,
            builder=builder,
            symbol=symbol,
            timeframe_minutes=timeframe_minutes,
            bars_count=bars_count,
            orchestrator=orchestrator,
            logger=logger,
            wakeup_payload=wakeup_payload,
        )
    except InsufficientBarsError as exc:
        logger.info("snapshot_skipped", reason="INSUFFICIENT_BARS", detail=str(exc))
        _console_status(f"跳过本轮: K 线数量不足，原因={exc}")
    except Exception as exc:  # noqa: BLE001 - 运行循环应记录日志并继续执行
        logger.info("runtime_error", detail=str(exc))
        _console_status(f"运行时异常: {exc}")


def _run_poll_loop(
    *,
    ingress,
    broker: MT5BrokerAdapter,
    mt5_module,
    builder: ContextBuilder,
    symbol: str,
    timeframe_minutes: int,
    bars_count: int,
    orchestrator: Orchestrator,
    logger: StructuredLogger,
) -> None:
    """Legacy poll mode: process first, then wait for the next trigger."""
    while True:
        _run_processing_cycle(
            broker=broker,
            mt5_module=mt5_module,
            builder=builder,
            symbol=symbol,
            timeframe_minutes=timeframe_minutes,
            bars_count=bars_count,
            orchestrator=orchestrator,
            logger=logger,
        )
        _console_status("等待下一轮触发...")
        payload = ingress.wait()
        if payload is None:
            _console_status("Ingress 已停止，退出循环")
            break


def _run_tick_http_loop(
    *,
    ingress,
    broker: MT5BrokerAdapter,
    mt5_module,
    builder: ContextBuilder,
    symbol: str,
    timeframe_minutes: int,
    bars_count: int,
    orchestrator: Orchestrator,
    logger: StructuredLogger,
) -> None:
    """Tick-http mode: wait for wake-up first, then process one runtime cycle."""
    while True:
        _console_status("等待下一轮触发...")
        payload = ingress.wait()
        if payload is None:
            _console_status("Ingress 已停止，退出循环")
            break

        _update_tick_info(
            f"symbol={payload.symbol}, time={payload.time_msc}, bid={payload.bid}, ask={payload.ask}, sequence={payload.sequence}"
        )
        _run_processing_cycle(
            broker=broker,
            mt5_module=mt5_module,
            builder=builder,
            symbol=symbol,
            timeframe_minutes=timeframe_minutes,
            bars_count=bars_count,
            orchestrator=orchestrator,
            logger=logger,
        )


def _resolve_trigger_config(
    runtime_cfg: configparser.SectionProxy | Dict[str, str],
    symbol: str,
    trigger_mode_override: Optional[str],
) -> TriggerConfig:
    """Resolve trigger configuration with CLI override over runtime.ini."""
    trigger_mode_str = trigger_mode_override or runtime_cfg.get("trigger_mode", "poll")
    return TriggerConfig.from_string(
        trigger_mode_str=trigger_mode_str,
        symbol=symbol,
        host=runtime_cfg.get("tick_host", "127.0.0.1"),
        port=int(runtime_cfg.get("tick_port", 8765)),
        queue_policy=runtime_cfg.get("queue_policy", "fifo"),
    )


def _test_order_linkage(broker: MT5BrokerAdapter, logger: StructuredLogger, symbol: str) -> bool:
    """测试下单链路是否正常。"""
    import importlib
    mt5 = importlib.import_module("MetaTrader5")

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        _console_status(f"无法获取 {symbol} 的报价，测试失败")
        return False

    test_price = float(tick.ask)
    test_sl = test_price - 10.0  # 止损设低10个点
    test_tp = test_price + 10.0  # 止盈设高10个点

    _console_status(f"测试下单链路: symbol={symbol}, price={test_price}")
    logger.info("order_linkage_test_started", symbol=symbol, test_price=test_price)

    result = broker.send_order(
        symbol=symbol,
        magic=999999,  # 测试用magic number
        order_type="BUY",
        volume=0.01,
        price=test_price,
        sl=test_sl,
        tp=test_tp,
        slippage=30,
        comment="LINKAGE_TEST",
    )

    success = bool(result.get("success", False))
    if success:
        ticket = result.get("ticket", 0)
        _console_status(f"测试订单发送成功! ticket={ticket}")
        logger.info("order_linkage_test_success", ticket=ticket, result=result)

        # 立即平仓（测试平仓链路）
        close_result = broker.close_position(
            ticket=ticket,
            close_price=float(tick.bid),
            closed_at=datetime.now(),
            close_reason="TEST_CLOSE",
        )
        if close_result.get("success"):
            _console_status("测试平仓成功")
            logger.info("position_close_test_success", ticket=ticket)
        else:
            _console_status(f"测试平仓失败: {close_result.get('reason')}")
            logger.error("position_close_test_failed", ticket=ticket, result=close_result)
    else:
        _console_status(f"测试订单发送失败: {result.get('reason')} (retcode={result.get('retcode')})")
        logger.error("order_linkage_test_failed", result=result)

    return success


def main() -> int:
    # 必须在开头声明全局变量
    global _console_file_logger

    parser = argparse.ArgumentParser(description="Run local-MT5 strategy sender")
    parser.add_argument("--config", type=str, default="config/runtime.ini")
    parser.add_argument("--once", action="store_true", help="只执行一次分析与决策")
    parser.add_argument("--poll-sec", type=float, default=2.0, help="循环模式下的轮询秒数")
    parser.add_argument("--bars-count", type=int, default=120, help="每次从 MT5 读取的 K 线数量")
    parser.add_argument(
        "--trigger-mode",
        type=str,
        default=None,
        choices=["poll", "tick_http"],
        help="Trigger mode override. Defaults to runtime.ini trigger_mode or poll",
    )
    parser.add_argument(
        "--test-order",
        action="store_true",
        help="测试下单链路是否正常（发送0.01手测试单并立即平仓）",
    )
    args = parser.parse_args()

    cfg = _load_config(args.config)
    runtime_cfg = cfg["runtime"] if "runtime" in cfg else {}
    symbol_cfg = cfg["symbol"] if "symbol" in cfg else {}
    timeframe_cfg = cfg["timeframe"] if "timeframe" in cfg else {}
    magic_cfg = cfg["magic"] if "magic" in cfg else {}
    trading_cfg = cfg["trading"] if "trading" in cfg else {}
    daily_cfg = cfg["daily_limits"] if "daily_limits" in cfg else {}

    log_path = runtime_cfg.get("log_path", "logs/runtime.log")
    state_path = runtime_cfg.get("state_path", "state/runtime_state.json")
    symbol = symbol_cfg.get("symbol", "XAUUSD")
    timeframe_minutes = int(timeframe_cfg.get("timeframe", 5))

    trigger_config = _resolve_trigger_config(
        runtime_cfg=runtime_cfg,
        symbol=symbol,
        trigger_mode_override=args.trigger_mode,
    )
    magic_number = int(magic_cfg.get("magic", DEFAULT_MAGIC_NUMBER))
    fixed_lots = float(trading_cfg.get("fixed_lots", DEFAULT_FIXED_LOTS))
    max_retries = int(trading_cfg.get("max_retries", DEFAULT_MAX_RETRIES))
    max_trades_per_day = int(daily_cfg.get("max_trades_per_day", 30))
    daily_profit_stop_usd = float(daily_cfg.get("daily_profit_stop_usd", 50.0))

    # 初始化控制台文件日志
    global _console_file_logger
    _console_file_logger = ConsoleFileLogger(log_dir="logs/console")

    # 启动控制台定时刷新
    _start_console_timer()

    _console_status("正在加载配置并准备连接本机 MT5 终端...")
    _console_status(
        f"运行参数: symbol={symbol}, timeframe={timeframe_minutes}m, magic={magic_number}, once={args.once}, poll_sec={args.poll_sec}, bars_count={args.bars_count}, trigger_mode={trigger_config.trigger_mode.value}"
    )

    logger = StructuredLogger(log_path=log_path)
    store = StateStore(state_path)

    broker = MT5BrokerAdapter(logger=logger)
    mt5_module = importlib.import_module("MetaTrader5")
    builder = ContextBuilder(symbol=symbol, timeframe=timeframe_minutes, magic_number=magic_number)
    orchestrator = Orchestrator(
        broker=broker,
        strategy_selector=StrategySelector(fixed_lots=fixed_lots, logger=logger),
        entry_gate=EntryGate(max_trades_per_day=max_trades_per_day, logger=logger),
        execution_engine=ExecutionEngine(broker=broker, max_retries=max_retries, logger=logger),
        protection_engine=ProtectionEngine(),
        daily_risk_controller=DailyRiskController(daily_profit_stop_usd=daily_profit_stop_usd),
        state_store=store,
        logger=logger,
        state=RuntimeState(day_key=datetime.now().strftime("%Y.%m.%d")),
        symbol=symbol,
        magic=magic_number,
    )

    _console_status("开始连接 MT5...")
    orchestrator.start()
    _console_status("MT5 连接成功")

    # 如果指定了测试下单，执行链路测试
    if args.test_order:
        _console_status("执行下单链路测试...")
        test_passed = _test_order_linkage(broker, logger, symbol)
        if not test_passed:
            _console_status("下单链路测试失败，请检查MT5设置")
            return 1
        _console_status("下单链路测试通过，继续正常运行")

    _console_status("开始进入策略分析循环。")

    ingress = None
    try:
        if args.once:
            _run_processing_cycle(
                broker=broker,
                mt5_module=mt5_module,
                builder=builder,
                symbol=symbol,
                timeframe_minutes=timeframe_minutes,
                bars_count=args.bars_count,
                orchestrator=orchestrator,
                logger=logger,
            )
            _console_status("--once 模式已完成，本次运行结束。")
        else:
            ingress = _create_ingress(
                trigger_config=trigger_config,
                poll_sec=args.poll_sec,
                symbol=symbol,
            )
            ingress.start()
            if trigger_config.trigger_mode == TriggerMode.POLL:
                _run_poll_loop(
                    ingress=ingress,
                    broker=broker,
                    mt5_module=mt5_module,
                    builder=builder,
                    symbol=symbol,
                    timeframe_minutes=timeframe_minutes,
                    bars_count=args.bars_count,
                    orchestrator=orchestrator,
                    logger=logger,
                )
            else:
                _run_tick_http_loop(
                    ingress=ingress,
                    broker=broker,
                    mt5_module=mt5_module,
                    builder=builder,
                    symbol=symbol,
                    timeframe_minutes=timeframe_minutes,
                    bars_count=args.bars_count,
                    orchestrator=orchestrator,
                    logger=logger,
                )
    finally:
        if ingress is not None:
            ingress.stop()
    logger.info(
        "run_completed",
        symbol=symbol,
        timeframe=timeframe_minutes,
        once=args.once,
        trigger_mode=trigger_config.trigger_mode.value,
    )
    _console_status("程序运行结束。")
    # 取消定时器并刷新剩余日志
    global _console_timer
    if _console_timer:
        _console_timer.cancel()
    _flush_console()
    # 关闭控制台文件日志
    if _console_file_logger is not None:
        _console_file_logger.close()
        _console_file_logger = None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
