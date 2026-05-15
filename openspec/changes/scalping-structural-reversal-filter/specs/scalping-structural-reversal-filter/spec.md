## ADDED Requirements

### Requirement: Configurable structural reversal filter
The system SHALL provide a configurable structural reversal filter for the scalping EA that can veto candidate buy or sell entries before orders are sent.

#### Scenario: Filter disabled
- **WHEN** the structural reversal filter is disabled
- **THEN** the EA MUST preserve the existing entry behavior for candidate buy and sell signals

#### Scenario: Filter enabled
- **WHEN** the structural reversal filter is enabled
- **THEN** the EA MUST evaluate the filter after an existing candidate entry condition is satisfied and before `SendBuyOrder()` or `SendSellOrder()` is called

### Requirement: Upward sprint danger detection
The system SHALL detect buy-side danger after a significant upward sprint when price is near the recent high zone and bearish reversal evidence is present, unless price has effectively broken out above the danger structure.

#### Scenario: Block buy near ceiling
- **WHEN** a buy candidate exists
- **AND** the recent closed-bar window shows an upward move greater than or equal to the configured sprint threshold
- **AND** the current price is in the configured upper portion of the recent high-low range
- **AND** bearish reversal evidence is present
- **AND** price has not effectively broken above the recent danger structure
- **THEN** the EA MUST skip the buy order

#### Scenario: Allow buy after upside breakout
- **WHEN** a buy candidate exists
- **AND** buy-side danger conditions were detected
- **AND** price effectively breaks above the recent high-side danger structure using the configured breakout rule
- **THEN** the EA MUST allow the existing buy order path to continue

#### Scenario: Allow buy without full danger evidence
- **WHEN** a buy candidate exists
- **AND** fewer than all required buy-side danger conditions are met
- **THEN** the EA MUST allow the existing buy order path to continue

### Requirement: Downward sprint danger detection
The system SHALL detect sell-side danger after a significant downward sprint when price is near the recent low zone and bullish reversal evidence is present, unless price has effectively broken down below the danger structure.

#### Scenario: Block sell near floor
- **WHEN** a sell candidate exists
- **AND** the recent closed-bar window shows a downward move greater than or equal to the configured sprint threshold
- **AND** the current price is in the configured lower portion of the recent high-low range
- **AND** bullish reversal evidence is present
- **AND** price has not effectively broken below the recent danger structure
- **THEN** the EA MUST skip the sell order

#### Scenario: Allow sell after downside breakout
- **WHEN** a sell candidate exists
- **AND** sell-side danger conditions were detected
- **AND** price effectively breaks below the recent low-side danger structure using the configured breakout rule
- **THEN** the EA MUST allow the existing sell order path to continue

#### Scenario: Allow sell without full danger evidence
- **WHEN** a sell candidate exists
- **AND** fewer than all required sell-side danger conditions are met
- **THEN** the EA MUST allow the existing sell order path to continue

### Requirement: Breakout release
The system SHALL provide a configurable breakout release condition that stops the structural reversal filter from blocking same-direction continuation entries after price accepts beyond the danger structure.

#### Scenario: Upside breakout release
- **WHEN** the current price or latest closed bar exceeds the recent high-side danger boundary by the configured breakout buffer
- **THEN** the EA MUST treat buy-side danger as released for that candidate entry

#### Scenario: Downside breakout release
- **WHEN** the current price or latest closed bar falls below the recent low-side danger boundary by the configured breakout buffer
- **THEN** the EA MUST treat sell-side danger as released for that candidate entry

#### Scenario: No breakout release
- **WHEN** price remains inside or rejects from the danger structure
- **THEN** the EA MUST continue applying the structural reversal filter normally

### Requirement: Closed-bar structure calculations
The system SHALL calculate sprint, range, and candle evidence from closed M5 bars so that the filter is not driven by incomplete candle shapes.

#### Scenario: Calculate recent sprint
- **WHEN** the filter evaluates a candidate entry
- **THEN** the EA MUST calculate recent movement from closed bars using the configured lookback window

#### Scenario: Calculate recent high-low range
- **WHEN** the filter evaluates a candidate entry
- **THEN** the EA MUST calculate the recent highest high and lowest low from closed bars using the configured lookback window

#### Scenario: Insufficient bars
- **WHEN** the chart does not have enough closed bars for the configured lookback window
- **THEN** the EA MUST not block the candidate trade solely because filter data is unavailable

### Requirement: Reversal evidence classification
The system SHALL classify bearish and bullish reversal evidence from candle rejection or short-term structure break conditions.

#### Scenario: Bearish evidence
- **WHEN** the latest closed-bar structure shows a configured long upper shadow, bearish engulfing or dark-cloud-like rejection, or a break below the recent short-term low
- **THEN** the EA MUST treat bearish reversal evidence as present for buy-side filtering

#### Scenario: Bullish evidence
- **WHEN** the latest closed-bar structure shows a configured long lower shadow, bullish engulfing or strong bullish rejection, or a break above the recent short-term high
- **THEN** the EA MUST treat bullish reversal evidence as present for sell-side filtering

### Requirement: Filter logging
The system SHALL log structural reversal filter decisions when debug logging is enabled.

#### Scenario: Log blocked buy
- **WHEN** the filter blocks a buy candidate
- **THEN** the EA MUST log the buy block reason including sprint direction, range position, and bearish evidence type

#### Scenario: Log blocked sell
- **WHEN** the filter blocks a sell candidate
- **THEN** the EA MUST log the sell block reason including sprint direction, range position, and bullish evidence type

#### Scenario: Log breakout release
- **WHEN** the filter allows a same-direction candidate because of breakout release
- **THEN** the EA MUST log the breakout direction and danger boundary when debug logging is enabled
