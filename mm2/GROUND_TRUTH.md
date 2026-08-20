# GROUND TRUTH — 100% true information, read at face value

*Tiers: **[T]** transcript verbatim · **[P]** problem statement verbatim · **[C]** template code (the grader's own classes) · **[O]** observed grader output (reproducible fact). No inferences here except where marked ⇒ as a direct logical consequence of the quote above it.*

---

## 1. What the game is

- **[P]** "Your market maker trades binary options (a.k.a. 'event contracts') on three daily-evolving underlyings": FED (fed funds rate), AJR (AjarAI), THR (Theriodic).
- **[P]** "Each option pays out 1.0 at expiry if the event it represents occurs, and 0.0 otherwise."
- **[C]** `expiry_valuation` = `1.0 if observable_value >= strike else 0.0` — the tie pays. `observable_value` = Σ leg.weight · value.
- **[P]** "although the `BinaryOption` class can represent options with any amount of legs, **in practice you will only encounter single-legged options, or 'spreads' on whether AjarAI or Theriodic has a higher valuation** like the third example above."
  - ⇒ The instrument universe is exactly: single-leg FED / AJR / THR, plus AJR-vs-THR **which-is-higher** spreads (weights ±1, strike 0 in the example "AjarAI valuation ≥ Theriodic valuation"). Anything more general is over-engineering.
- **[C]** `RATE_STRIKE_GRID = 0.25` ⇒ FED strikes live on the 0.25 grid — tie mass at strikes is macroscopic for FED.

## 2. The exact dynamics (this is the data-generating code, not a model)

- **[C]** Rate step: `tilt = strength·(target − r)`; `up = clip(p_up + tilt, 0, 1)`; `down = clip(p_down − tilt, 0, 1 − up)` — note down is clipped **after** up, to `1 − up`. Stay probability = `1 − up − down` (params validate `p_up + p_down ≤ 1`). New rate = `max(round(r ± 0.25, 2), 0)`.
- **[C]** Company step: `log_return = drift + rate_beta·rate_change + sector_beta·sector_shock + idio`, with `rate_change = round(r_new − r_old, 2)` (the **realized** rate move, shared by both companies), `sector_shock ~ N(0, sector_std_dev)` (**shared** by both companies), `idio ~ N(0, idio_std_dev)` (per company). New value = `round(value·exp(log_return), 2)`.
  - ⇒ Conditional on the rate path's total change, the two companies' T-step log-returns are exactly bivariate normal with covariance `T · β_sec,A · β_sec,T · σ_sec²`. Spread P(AJR ≥ THR) is a closed-form normal CDF on the log-ratio. **No Monte Carlo is needed anywhere.**
- **[T]** "Generally, as interest rates fall, the valuations of moonshot startups rise and vice versa." ⇒ the true `rate_beta`s are **negative** — an officially given sign to sanity-check estimates against.
- **[T]** "These three underlyings will vary in value according to a joint distribution, **which you'll have to estimate from historical returns**." ⇒ estimation from `MarketHistory` is the intended task, officially.

## 3. Order mechanics — the two pipelines

- **[P]** RFQ: "the exchange will request quotes from all participating market makers, and **route the order to the highest bid or lowest offer it receives, splitting up the order if necessary**. Therefore, your quote method should **return the most competitive prices and quantities you are able to trade on**. Note that you will not know ahead of time whether the RFQ is a buy or sell order."
  - ⇒ Only one side of our quote executes per RFQ. Best price wins the flow. Competitiveness is *instructed*, not optional flavor.
- **[P]** FOK: "give you all the information up front, and it is up to you whether you want to trade them ... **If multiple market makers denote that they want to trade an FOK order, it will be broken up between them.**"
- **[C]** `respond_to_fok` returns **bool**; template comment: "You cannot accept part of it, and accepting does not guarantee you `fok_order.quantity`".
- **[C]** `Quote` validation: `0 ≤ bid < offer ≤ 1`, whole pennies, positive integer quantities.
- **[C]** `quote(option, counterparty_id)` — **the counterparty's identity is given to us on every RFQ**. `FokOrder` carries `counterparty_id` too. `on_trade` reports `counterparty_id` of every fill.
- **[C]** Template comment on `price_option`: called "whenever you quote or price a FOK, **and by the grader to log what you thought an option was worth**, so keep it free of side effects."
- **[O]** Counterparty ids repeat within a session (TC2: 689497 sends both the sell-6 and buy-2 RFQs; TC3/4: 482453, 469703, 808858 appear repeatedly). ⇒ Counterparties are persistent actors within a session.

## 4. The official strategy guidance (the sentences we under-weighted)

- **[T]** "Your market-making bot should balance the risk of trading orders, being mindful of both **your theoretical value** for the options and **the position you already hold**."
- **[T]** "You'll be competing in a variety of scenarios with both **progressively more difficult competitors and more difficult trading conditions**."
- **[T]** "So, **you'll want to find ways to adapt your behavior based on information you get from your counterparties**."
  - ⇒ Read literally with §3: the API hands us `counterparty_id` at every quote, every FOK, every fill. **Per-counterparty adaptation is the officially designated edge.** (Our previous bots adapted *globally* per session — one regime for all counterparties — which poisons quoting toward benign flow whenever one informed actor appears.)
- **[P]** "These tests will also vary in difficulty, **including via different counterparties and different competing market makers**."
  - ⇒ Difficulty axes = who trades with us + who quotes against us. Both are observable in-session through ids and fills.
- **[T]** "we've structured the competition to try to balance the scales in favor of competitors that also **draw on their own ideas**."
- **[O]** Sessions contain a **mix** of counterparty types simultaneously (TC4: 757814 lowballs junk, 808858 picks off at 0.99 vs theo 1.0, 578477 trades near-fair, 469703 lowballs) — confirming per-cp treatment beats global regimes.

## 5. Tests, scoring, bankruptcy — the rules

- **[P]** Test 1 = THEO: scores `price_option_from_parameters` given **true** MarketParameters. Tests 2–4 = VERBOSE: "full points ... so long as your code does not error and your MarketMaker does not go bankrupt." Tests 5–20 = SCORED: "**full credit for being the top market maker in the session by PnL, zero credit for going bankrupt (or code errors), and partial credit for avoiding bankruptcy.**"
- **[O]** Partial credit law (fitted, 64 observations, 0 violations, n∈{1,2,3}): score = 0.4 + 0.6·(competitors out-earned ÷ competitors). No headroom above 1.00 — $79 vs $12 scored exactly 1.00. Aggregation = plain sum + 4.0 (verified to the cent on four runs).
- **[P]** Bankruptcy: "Every time you do a trade, your balance will decrease by **the maximum loss of your trade**" (buy q@p locks q·p; sell locks q·(1−p)). "Cash solvency is checked **at the end of each day**. First, any payoffs associated with expired options will be credited — note that this process **can only increase your balance**. At this point if your cash balance is below zero, you will be marked as bankrupt, and the session will end early."
  - ⇒ Intraday negative is survivable; multi-day locks accrue unoffset until expiry; ruin (0) < last place (0.4).
- **[O]** Tests are fixed-seed (identical logs/PnLs across runs wherever behavior didn't change). Opponent roster observed: Stalemate Quoter (quotes 0.00/1.00, big size), Fixed Width 0.05/0.1/0.25 (theo ± w/2), Lattice, Situational Unawareness, Mongoose.
- **[O]** RFQ fills at tied best price split equally and are size-invariant (our 20 vs 120 quoted → identical fills of 3). Allocation rule beyond this: not exposed.

## 6. The meta-fact

- The challenge is designed for **~5–8 hours** of work. ⇒ The intended solution is: exact pricer + honest estimation + competitive two-sided quoting + inventory/cash discipline + **per-counterparty adaptation**. Every one of those elements is named in the official text. Nothing in the official text requires regime machines, λ-books, tournament variance theory, or auction theory.
