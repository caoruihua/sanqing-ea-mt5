## Context

`mt5/剥头皮脚本.mq5` is a single-file XAUUSD M5 scalping EA. It currently decides direction from price versus EMA, then enters from pullback, strong-trend, or sustained-trend conditions. That works for continuation, but it can still approve entries after a fast intraday move has already reached a likely turning zone.

The repository already contains a broader reversal strategy concept in `reversal-sprint-end-filter`: a recent 24-bar sprint, reversal candle evidence, and recent high/low context. This change adapts that idea as a defensive filter for the scalping EA. The filter will reject same-direction entries only; it will not create reverse orders.

Current order path:

```text
OnTick
  -> environment/time/risk/position checks
  -> GetTrendDirection()
  -> CheckPullbackEntry() or CheckSustainedTrendEntry()
  -> SendBuyOrder() / SendSellOrder()
```

Target order path:

```text
OnTick
  -> existing checks
  -> existing signal logic
  -> structural reversal danger filter
       -> block unsafe buy/sell
       -> allow breakout continuation beyond the danger zone
       -> otherwise allow existing order code
```

## Goals / Non-Goals

**Goals:**

- Prevent buy entries near intraday ceiling conditions after extended upward moves.
- Prevent sell entries near intraday floor conditions after extended downward moves.
- Allow the original trend-following entries to resume after price effectively breaks through the danger zone.
- Keep the current scalping strategy intact when the filter is disabled or no danger zone is detected.
- Make filter behavior observable through debug logs.
- Keep the change local to the single-file EA and avoid new dependencies.

**Non-Goals:**

- Do not add reverse trading after detecting a danger zone.
- Do not rewrite the EMA trend, pullback, sustained-trend, take-profit, stop-loss, daily PnL, or time-control systems.
- Do not merge this EA into the larger `mt5-ea` architecture.
- Do not optimize final parameter values without backtest evidence.

## Decisions

### 1. Use a three-part danger model

The filter should treat a trade as dangerous only when the setup has enough evidence of a structural turning zone:

```text
recent sprint + extreme zone + reversal evidence = block same-direction entry
```

For buys:

```text
upward sprint + current price near recent high + bearish reversal evidence = block buy
```

For sells:

```text
downward sprint + current price near recent low + bullish reversal evidence = block sell
```

Rationale: A single signal is too noisy. A long upper shadow alone can occur mid-trend, and a strong 2-hour move alone can continue. Combining conditions reduces false blocks.

Alternative considered: block only by distance from EMA. Rejected because the current strategy intentionally uses EMA deviation for strong-trend entries, so an EMA-only block would conflict with the original continuation logic.

### 2. Measure recent sprint over a configurable M5 bar window

Default to a 24-bar M5 window, matching roughly 2 hours:

```text
priceMove = close[1] - close[window + 1]
```

Use an ATR multiple as the default sprint threshold, with a fixed-dollar fallback or minimum if needed. ATR adapts to changing XAUUSD volatility better than a single fixed-dollar threshold.

Alternative considered: use daily open-to-current move. Rejected because the user problem is intraday structure near local turns, not only full-day direction.

### 3. Measure high/low zone by position inside the recent range

Compute:

```text
rangePosition = (currentPrice - lowWindow) / (highWindow - lowWindow)
```

- Buy danger zone: `rangePosition >= highZoneRatio`, default around `0.80`.
- Sell danger zone: `rangePosition <= lowZoneRatio`, default around `0.20`.

Rationale: This identifies whether the EA is chasing near the top or bottom of the recent structure, independent of the absolute price level.

Alternative considered: require new daily high or daily low. Rejected because many painful entries happen near a local 1-2 hour extreme without being the literal daily high/low.

### 4. Confirm reversal danger with candle or micro-structure evidence

Bearish evidence for blocking buys should include one or more of:

- Long upper shadow on the latest closed bar.
- Bearish engulfing or dark-cloud-like close into the prior bullish candle body.
- Break below the recent 3-5 bar low after an upward sprint.

Bullish evidence for blocking sells should include one or more of:

- Long lower shadow on the latest closed bar.
- Bullish engulfing or strong close into the prior bearish candle body.
- Break above the recent 3-5 bar high after a downward sprint.

Rationale: The filter should distinguish "extended but still trending" from "extended and beginning to reject the extreme."

Alternative considered: require only long-shadow candles. Rejected because some reversals are clean structure breaks without obvious wick dominance.

### 5. Place the filter after candidate signal creation and before order send

The existing signal checks should continue to decide whether the EA wants to trade. The new filter then vetoes the candidate trade.

Rationale: This placement keeps the filter independent from the existing entry logic and ensures it applies uniformly to pullback, strong-trend, and sustained-trend entries.

Alternative considered: integrate directly inside `GetTrendDirection()`. Rejected because trend direction should remain a direction classifier, not a trade permission gate.

### 6. Treat confirmed breakout as a danger-zone release

The danger zone should not become a permanent no-trade area. If price breaks through the structure that created the danger zone, the filter should stop blocking same-direction entries.

For buys, an upward breakout can be defined as price exceeding the recent high-window boundary by a configurable buffer, or a closed M5 bar closing above that boundary:

```text
current ask or close[1] > highWindow + breakoutBuffer
```

For sells, a downward breakout can be defined as price falling below the recent low-window boundary by a configurable buffer, or a closed M5 bar closing below that boundary:

```text
current bid or close[1] < lowWindow - breakoutBuffer
```

Rationale: A structural danger zone means "do not chase into likely rejection." Once the market accepts prices beyond that zone, the original continuation thesis becomes valid again.

Alternative considered: keep blocking until the sprint window resets. Rejected because it would miss valid breakout continuation trades after a real level break.

## Risks / Trade-offs

- Reduced trade frequency -> The filter will intentionally skip some valid continuation trades near extremes. Mitigation: make it configurable and log each block reason.
- Missed breakout continuation -> If the filter does not distinguish rejection from breakout, it may block valid trend continuation after level acceptance. Mitigation: add a configurable breakout release condition.
- Parameter sensitivity -> ATR multiple, window size, and zone ratio may need backtesting. Mitigation: expose inputs and keep conservative defaults.
- False confidence from candle patterns -> Wick/engulfing signals can be noisy on M5. Mitigation: require sprint and zone context before candle evidence can block trades.
- Implementation risk in MQL5 indexing -> Closed-bar indices must avoid current-forming bar noise. Mitigation: use closed bars for candle structure and keep current tick only for order-side price checks.
- Existing Chinese filename/tool encoding friction -> CLI output may display mojibake. Mitigation: verify compile behavior in MetaEditor rather than relying on console-rendered comments.

## Migration Plan

1. Add disabled-by-switch or enabled-by-default configurable filter inputs.
2. Implement helper calculations in `mt5/剥头皮脚本.mq5` without changing existing order functions.
3. Insert the veto check immediately before `SendBuyOrder()` or `SendSellOrder()`.
4. Compile with MetaEditor.
5. Run visual/log review in strategy tester to confirm blocked entries are explained.
6. Roll back by disabling the input flag if trade frequency becomes too low.

## Open Questions

- Should the default filter be enabled immediately, or shipped disabled for first backtest comparison?
- Should the sprint threshold use ATR only, fixed USD only, or `max(ATR multiple, fixed USD)`?
- Should micro-structure break confirmation be mandatory, or one of several reversal evidence options?
- Should breakout release require an intra-tick price break, a closed-bar confirmation, or both as configurable modes?
- Should the danger window be 24 bars only, or support separate 24-bar and 48-bar checks?
