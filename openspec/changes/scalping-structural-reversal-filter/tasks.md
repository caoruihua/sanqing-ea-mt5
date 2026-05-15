## 1. Inputs and Data Helpers

- [x] 1.1 Add structural reversal filter input parameters to `mt5/剥头皮脚本.mq5`
- [x] 1.2 Add closed-bar availability checks for the configured lookback window
- [x] 1.3 Add helper logic to calculate recent closed-bar movement, highest high, lowest low, and range position
- [x] 1.4 Add helper logic to calculate ATR or an equivalent volatility threshold for sprint detection
- [x] 1.5 Add configurable breakout release parameters for boundary buffer and confirmation mode

## 2. Reversal Evidence Detection

- [x] 2.1 Implement bearish evidence detection for long upper shadow on closed bars
- [x] 2.2 Implement bullish evidence detection for long lower shadow on closed bars
- [x] 2.3 Implement bearish and bullish engulfing or rejection-style candle checks
- [x] 2.4 Implement optional short-term structure break checks using recent 3-5 closed bars
- [x] 2.5 Implement upside and downside breakout release detection against recent danger boundaries

## 3. Trade Veto Integration

- [x] 3.1 Implement buy-side danger evaluation for upward sprint plus high-zone plus bearish evidence
- [x] 3.2 Implement sell-side danger evaluation for downward sprint plus low-zone plus bullish evidence
- [x] 3.3 Apply breakout release so confirmed upside breakouts allow buys and confirmed downside breakouts allow sells
- [x] 3.4 Insert the filter after candidate signal approval and before `SendBuyOrder()` or `SendSellOrder()`
- [x] 3.5 Preserve existing behavior when the filter is disabled or insufficient bars are available

## 4. Logging and Safety

- [x] 4.1 Add debug logs for blocked buy candidates with sprint, range position, and evidence reason
- [x] 4.2 Add debug logs for blocked sell candidates with sprint, range position, and evidence reason
- [x] 4.3 Add debug logs for breakout release when the filter allows same-direction continuation
- [x] 4.4 Ensure no reverse order is opened by the filter
- [x] 4.5 Ensure existing daily PnL, time-control, cooldown, and open-position checks remain unchanged

## 5. Verification

- [x] 5.1 Compile `mt5/剥头皮脚本.mq5` in MetaEditor
- [ ] 5.2 Run strategy tester or log review with the filter enabled to confirm buy blocks near upward sprint highs
- [ ] 5.3 Run strategy tester or log review with the filter enabled to confirm sell blocks near downward sprint lows
- [ ] 5.4 Run strategy tester or log review to confirm upside breakout releases buy blocking and downside breakout releases sell blocking
- [ ] 5.5 Run comparison with the filter disabled to confirm existing entry behavior is preserved
