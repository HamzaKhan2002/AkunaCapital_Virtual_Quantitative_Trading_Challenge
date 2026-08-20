# REFERENCE.md — Akuna Capital Virtual Quant Trading Challenge 2026
*Single source of mathematical and mechanical truth. Mark anything unverified as `UNKNOWN — verify against live prompt`.*

---

## NOTATION (enforced throughout this file and all code)

| Symbol | Meaning |
|--------|---------|
| $S$ | Spot/underlying valuation |
| $K$ | Strike |
| $T$ | Steps to maturity (discrete) |
| $t$ | Current step |
| $\sigma$ | Per-step noise standard deviation |
| $u$ | Up-move step size |
| $d$ | Down-move step size |
| $p$ | Up-move probability |
| $q = 1-p$ | Down-move probability (never confused with inventory) |
| $V$ | Theoretical option value |
| $\Delta, \Gamma, \Theta$ | Greeks (finite-difference; see §5) |
| $\mathbb{1}$ | Indicator function |
| $\Phi$ | Standard normal CDF |
| $n_u$ | Number of up-moves in a path |
| $b, a$ | Bid, ask |
| $m$ | Quoted midpoint / reservation price |
| $w$ | Half-spread |
| $\lambda$ | Fill intensity |
| $\gamma_{\text{risk}}$ | Risk-aversion parameter (never Greek Gamma) |
| $Q$ | Inventory (signed: long > 0, short < 0) |
| $\epsilon$ | Per-step Gaussian noise term |

*Deviation from the team notation spec: inventory is $Q$ (capital), keeping lowercase $q = 1-p$ for the binomial down-probability — this matches both textbook convention and the 2025 API field `down_move_probability`. If a formula ever needs both in lowercase, use $p_\downarrow$ for the down-probability per the spec.*

---

## §1 — VERIFIED 2026 MECHANICS
*Source: official 2026 video transcript (highest tier) + live Reddit r/quantfinance 2026-08-17*

### 1.1 Instruments
- **Binary options** (also called "event contracts") on **three underlyings**:
  - Fed funds rate
  - Ajar AI valuation (fictional private AI company)
  - Theory AI valuation (fictional private AI company)
- Settlement: **0 or 1** based on whether the specified event occurs at expiry.
- Options conceptually priced as **probabilities**, not expected payoffs of `max(·)`.

### 1.2 Underlying Dynamics
- Underlyings follow a **joint distribution** — explicitly correlated. Transcript: *"as interest rates fall, the valuations of moonshot startups rise and vice versa."*
- Distribution must be **estimated from historical returns** provided in the problem.
- Individual dynamics (from 2025 analogue, Luthra notebook — verify against live prompt):
  - Binomial random walk: each step $S_{t+1} = S_t + u$ (prob $p$) or $S_t - d$ (prob $q$)
  - Drift-free (martingale): $p \cdot u = q \cdot d$
  - Plus i.i.d. Gaussian noise per step: $\epsilon_t \sim N(0, \sigma^2)$

### 1.3 Task Structure
- **Two duties**: (1) provide continuous two-sided quotes (bid + ask + quantities) and (2) respond to incoming customer buy/sell orders.
- Must manage **position/inventory** mindfully — bankruptcy = automatic fail for that scenario.
- **Scenarios escalate**: progressively harder competitors and harder conditions.
- Must **adapt** based on counterparty information (transcript: "find ways to adapt your behavior based on information you get from your counterparties").

### 1.4 Format / Scoring — evidence tiers kept separate
**STATED (problem statement, verbatim)**: *"You will receive full credit for being the top market maker in the session by `PnL`, zero credit for going bankrupt (or code errors), and partial credit for avoiding bankruptcy. These tests will also vary in difficulty, including via different counterparties and different competing market makers."* The statement defines only three anchors and never specifies what "partial" scales with.

**`CONFIRMED` for $n \in \{1,2,3\}$ — 64 observations (16 SCORED × 4 logged runs), 0 violations. Reproduce: `python audit_scoring.py`.**
$$\text{score} = 0.4 + 0.6\cdot\frac{\#\{\text{competitors we out-earn}\}}{\#\{\text{competitors}\}}$$
Evidence detail: distinct $n$ observed = {1,2,3}; distinct fractions = {0, 1/3, 1/2, 2/3, 1} → scores {0.40, 0.60, 0.70, 0.80, 1.00}. Boundary `beaten=0` → exactly 0.40 in **26/26** cases (including with negative PnL); boundary `beaten=n` → exactly 1.00 in **10/10**. **No headroom above 1.00**: Run 5 TC15 earned $79.08 vs best opponent $11.72 (6.7×) and still scored exactly 1.00 — margin of victory is worth nothing.
`UNKNOWN` (untested): behaviour at $n \ge 4$; PnL ties; the bankruptcy→0 anchor (stated in the spec, never empirically hit).

**`CONFIRMED` — AGGREGATION IS A SIMPLE UNWEIGHTED SUM.** Verified arithmetically against four independent reported totals: Run1 9.20+4.0=**13.20**, Run2 9.80+4.0=**13.80**, Run3 10.00+4.0=**14.00**, Run5 11.20+4.0=**15.20** — all exact. No difficulty weighting, no best-N-of-16, no threshold. **Strategic consequence: every test is worth exactly the same; optimise expected score uniformly and never prioritise "hard" tests.** A solvent bot's floor is $4 + 0.4\times16 = 10.4$; max is 20.

**EXACT expectation (linearity; no distributional assumption)**:
$$E[\text{score}] = 0.4 + 0.6\cdot\frac{1}{n}\sum_{i=1}^{n} P(\text{PnL}_{us} > \text{PnL}_i)$$
Consequence: marginal score comes from beating the **next-weakest** opponent, not the leader. Any $\Phi(\cdot)$ form is an approximation of a single pairwise term under normality — `HYPOTHESIS`, not law.

Other format facts (live 2026 sources): HackerRank, exit/re-enter allowed; 1 THEO + 3 VERBOSE (full points iff no error and no bankruptcy) + 16 SCORED; two rounds; resubmission allowed before deadline.

### 1.4b Bankruptcy timing — verbatim, and why it bounds risk-taking
*"Every time you do a trade, your balance will decrease by the maximum loss of your trade... Cash solvency is checked at the end of each day. First, any payoffs associated with expired options will be credited — note that this process can only increase your balance. At this point if your cash balance is below zero, you will be marked as bankrupt, and the session will end early."*
- Intraday negative balance is survivable; the test is once per day, **after** expiry credits.
- Credits arrive **only** at expiry → debits on multi-day options accumulate with no offset for the option's whole life.
- Failure path: lever up on day $t$ using $T$-day options; days $t..t{+}T$ accrue locks; a large fill lands before any expiry matures → end-of-day check fails → score 0.
- **Risk-taking bound**: last place scores 0.4, bankruptcy scores 0, so extra variance pays only if $0.6\,P(\text{rank gain}) > 0.4\,P(\text{ruin})$, i.e. $P(\text{gain})/P(\text{ruin}) > 2/3$. The worst-case margin ledger (§5.7) must never be relaxed to fund a variance play.

### 1.5 RESOLVED 2026-08-18 — live starter code supersedes §§2–6 modeling assumptions
All pre-live unknowns are resolved (full detail: MEMORY.md "LIVE PROMPT RESOLVED"). Headlines:
- Tie convention **`>=`** (`expiry_valuation`); payoff = $\mathbb{1}[\sum_i w_i S_{i,T} \ge K]$ with weighted legs; AJR-vs-THR spread options exist.
- Dynamics are a **factor model**, not 2025 binomial+noise: FED = mean-reverting 0.25-grid walk (linear tilt, clamped, floor 0, stay-probability allowed); AJR/THR = lognormal with drift + rate_beta·Δr + sector_beta·(shared sector shock) + idio, rounded 2dp.
- Key pricing reduction: companies load on the rate only via $r_T - r_0$ ⇒ exact pricer = DP over the rate grid × conditional bivariate-lognormal closed forms (implemented + MC-validated in Market_Maker.py / validate_live.py).
- Margining: every trade immediately debits its **maximum loss** (buy: $q\cdot p$; sell: $q\cdot(1-p)$); expiry credits only add back; solvency checked end-of-day. §5.7's worst-case logic maps 1:1.
- Scoring: 1 THEO (pricing accuracy) + 3 VERBOSE (no-crash/no-bankruptcy) + 16 SCORED (top PnL = full, bankrupt/error = zero, solvent = partial).
The binomial+Gaussian machinery in §§2–4 remains as reference for the audit trail; the live model's math lives in the code and MEMORY.md.

---

## §2 — BINARY OPTION MATHEMATICS

### 2.1 Payoff
For a binary call with strike $K$ on underlying $S$ with terminal value $S_T$:
$$V_{\text{call}} = \mathbb{1}[S_T > K] \qquad V_{\text{put}} = \mathbb{1}[S_T < K]$$
Settlement values: 0 or 1 (not `max(S-K, 0)`).

### 2.2 Fair Value = Probability
$$V_{\text{binary call}} = P(S_T > K)$$
$$V_{\text{binary put}} = P(S_T < K) = 1 - V_{\text{binary call}} \text{ (no ties in continuous model)}$$

This is the key distinction from regular options — **no expectation over a positive region, just a probability mass**.

### 2.3 Pricing Under Binomial + Gaussian Noise
Terminal price from the binomial tree (without noise):
$$S_T^{(n_u)} = S_t + n_u \cdot u - (T - n_u) \cdot d, \quad n_u = 0, 1, \ldots, T$$
$$P\!\left(N_u = n_u\right) = \binom{T}{n_u} p^{n_u} q^{T-n_u}$$

Total accumulated Gaussian noise (Gaussians are additive in variance):
$$\epsilon_{\text{total}} = \sum_{i=1}^{T} \epsilon_i \sim N(0,\ T \sigma^2)$$

Fair value for binary call:
$$V = \sum_{n_u=0}^{T} \binom{T}{n_u} p^{n_u} q^{T-n_u} \cdot P(S_T^{(n_u)} + \epsilon_{\text{total}} > K)$$
$$= \sum_{n_u=0}^{T} \binom{T}{n_u} p^{n_u} q^{T-n_u} \cdot \Phi\!\left(\frac{S_T^{(n_u)} - K}{\sqrt{T}\,\sigma}\right)$$

where $\Phi$ is the standard normal CDF.

For binary put, replace $\Phi(\cdot)$ with $1 - \Phi(\cdot)$.

**σ = 0 edge case**: the summand becomes the indicator $\mathbb{1}[S_T^{(n_u)} > K]$ — pure binomial probability. Handle $S_T^{(n_u)} = K$ explicitly per the tie convention (§2.6); do not evaluate $\Phi(0/0)$.

**Noise effect — pull toward one-half (replaces any vanilla "convexity" intuition)**: binaries are step functions, not convex payoffs, so Jensen's inequality does not apply. Each component $\Phi(z_{n_u})$ moves monotonically toward $\Phi(0) = \tfrac12$ as $\sigma$ grows, so noise **raises OTM values and lowers ITM values**. Omitting noise therefore biases prices with a moneyness-dependent sign (unlike vanillas, where omission always underprices). Always model noise when $\sigma > 0$.

### 2.4 Multi-Underlying Binary Options (UNKNOWN — prepare for)
If an option pays 1 iff *both* $S_T^{(A)} > K_A$ *and* $S_T^{(B)} > K_B$, the joint distribution is required:
$$V = P(S_T^{(A)} > K_A,\ S_T^{(B)} > K_B)$$
Concrete approaches, in order of preference:
1. **Joint step model**: per-step outcomes $\{uu, ud, du, dd\}$ with probabilities matching the marginals and the estimated increment correlation; price on the joint lattice with bivariate noise.
2. **Gaussian copula on terminals**: approximate each marginal terminal CDF (§3.3), couple with the estimated correlation, evaluate via the bivariate normal CDF (`scipy.stats.multivariate_normal` — availability in the HackerRank env presumed from 2025's scipy import, verify).
3. Monte Carlo over the joint process only if the structure resists both.
Estimate correlation on **increments** (returns), not levels (§3.5, §6.2).

### 2.5 Put-Call Parity for Binaries
$$V_{\text{call}}(K) + V_{\text{put}}(K) = 1 - P(S_T = K)$$
With continuous noise ($\sigma > 0$, no rounding), $P(S_T = K) = 0$ and parity is exactly $1$ — use as a pricer sanity check. With $\sigma = 0$ or grid-rounded prices, ties carry positive probability and parity depends on the payoff convention (§2.6).

### 2.6 Ties and Discreteness — `UNKNOWN — verify against live prompt`
- Is the call payoff $\mathbb{1}[S_T > K]$ or $\mathbb{1}[S_T \ge K]$? Read it off the live starter code (`expiry_valuation` or equivalent) before pricing anything.
- The 2025 simulator **rounded valuations to 2 decimals every step** — terminal prices live on a 0.01 grid, so $P(S_T = K) > 0$ for on-grid strikes *even with noise*.
- With $\sigma = 0$, lattice nodes can land exactly on integer strikes; the tie mass is macroscopic.
- A wrong tie convention shifts every near-the-money price by up to the tie mass — a systematic, exploitable pricing error.

### 2.7 Moments and a Fast Sanity Approximation
Per-step increment $X \in \{+u, -d\}$ with $E[X] = pu - qd = 0$; define $c := pu = qd$. Then:
$$\text{Var}[X] = pu^2 + qd^2 = c\,(u+d), \qquad E[X^3] = c\,(u^2 - d^2) \;(\ne 0 \text{ iff } u \ne d)$$
$$E[S_T] = S_t \text{ (martingale)}, \qquad \text{Var}[S_T] = T\left(c(u+d) + \sigma^2\right)$$
CLT approximation (sanity check / speed fallback ONLY):
$$V \approx \Phi\!\left(\frac{S_t - K}{\sqrt{T\,(c(u+d) + \sigma^2)}}\right)$$
It ignores binomial skew (present iff $u \ne d$) and discreteness; error is largest far from the money and at small $T$. The exact mixture pricer is $O(T)$ per option — cheap enough to always use for actual quoting. Unlike 2025 vanillas, single-underlying binaries need **no** Monte Carlo or quantile quadrature at all.

---

## §3 — UNDERLYING PROCESS

### 3.1 Individual Underlying State (from Luthra 2025, verify in live prompt)
Each `Underlying` object provides:
- `valuation` $= S_t$
- `up_move_step` $= u$
- `down_move_step` $= d$
- `up_move_probability` $= p$
- `down_move_probability` $= q$
- `noise_std_dev` $= \sigma$ (per-step)

Martingale constraint (zero drift): $p \cdot u = q \cdot d$ (validated in `Underlying.__post_init__`).

### 3.2 Joint Distribution
The three underlyings are correlated. The correlation structure must be estimated from the historical returns dataset provided in the problem. Key assumption from transcript: negative correlation between rates and AI valuations.

**For independent binary options on individual underlyings**: joint distribution only needed for multi-underlying options.
**For correlated joint options**: must model the full joint process — likely via a copula or a correlated multi-variate binomial. UNKNOWN until live prompt confirms option types.

### 3.3 Terminal Price Distribution
At time $T$ steps ahead, with current price $S_t$:
- Possible terminal prices: $S_T^{(n_u)} = S_t + n_u u - (T-n_u)d$, $n_u \in \{0,...,T\}$
- Each with probability $\binom{T}{n_u}p^{n_u}q^{T-n_u}$
- Plus noise: $\epsilon_{\text{total}} \sim N(0, T\sigma^2)$

The distribution is therefore a **mixture of Gaussians**, where each component has mean $S_T^{(n_u)}$ and variance $T\sigma^2$, weighted by the binomial probabilities.

### 3.4 Boundary and Discreteness Caveats (model vs. simulator)
The 2025 simulator applied `max(valuation, 0)` **and** rounded to 2 decimals at *every step*. If 2026 keeps either behavior (`UNKNOWN — verify`):
- The floor breaks the martingale property near $S \approx 0$ (flooring adds upward drift) and invalidates the single-Gaussian noise-sum shortcut there — a floor-blind pricer overstates downside mass, biasing puts up / calls down.
- Materiality test: negligible iff $S_t - T\,d - 4\sqrt{T}\,\sigma \gg 0$. Check per underlying; the **Fed funds rate** plausibly lives near zero, where this bites.
- Per-step rounding puts $S_T$ on a 0.01 grid → tie mass at on-grid strikes (§2.6).
- Do not assume all three underlyings share one process family: a rate and two valuations may be parameterized differently (mean reversion is a standard rates choice). `UNKNOWN — verify each underlying's params in the live prompt.`

### 3.5 Parameter Estimation from Historical Returns
Branch on what the live API provides (2025 handed $p, u, d, \sigma$ directly in the `Underlying` object; the 2026 transcript says "estimate from historical returns" — possibly only the joint/correlation structure needs estimating. `UNKNOWN — verify`).
If per-underlying parameters must be estimated from increments $\Delta S_t$:
1. Increments are a two-component Gaussian mixture: $N(+u, \sigma^2)$ w.p. $p$, $N(-d, \sigma^2)$ w.p. $q$.
2. If $\sigma \ll u + d$: classify increments by sign (or 2-means), estimate $u, d$ as cluster means, $p$ as the up-cluster weight, $\sigma$ as pooled within-cluster std. If clusters overlap, refine with EM.
3. Check (don't force) drift-freeness: report $|\hat p\hat u - \hat q\hat d|$; a material deviation means the model family is wrong — re-read the prompt.
4. Correlation: estimate on increments (returns), not levels. Record standard errors of ALL estimates — they feed the §5.8 spread floor.

---

## §4 — BINARY OPTION GREEKS

Greeks are sensitivities of $V$ (a probability) to state and parameters. Because the pricer is a finite sum of normal CDFs, all Greeks below are **closed-form and exact** for $\sigma > 0$ — prefer them to finite differences. Notation: $z_{n_u} = \dfrac{S_T^{(n_u)} - K}{\sqrt{T}\,\sigma}$, $w_{n_u} = \binom{T}{n_u}p^{n_u}q^{T-n_u}$, $\phi$ = standard normal pdf.

### 4.1 Analytic Greeks (primary, $\sigma > 0$)
$$\Delta = \frac{\partial V}{\partial S} = \frac{1}{\sqrt{T}\,\sigma}\sum_{n_u} w_{n_u}\,\phi(z_{n_u}) \quad (> 0 \text{ for calls};\ \Delta_{\text{put}} = -\Delta_{\text{call}})$$
$$\Gamma = \frac{\partial^2 V}{\partial S^2} = -\frac{1}{T\sigma^2}\sum_{n_u} w_{n_u}\, z_{n_u}\,\phi(z_{n_u})$$
$$\nu = \frac{\partial V}{\partial \sigma} = -\frac{1}{\sigma}\sum_{n_u} w_{n_u}\, z_{n_u}\,\phi(z_{n_u}) = T\,\sigma\,\Gamma$$
The identity $\nu = T\sigma\Gamma$ is a free consistency check between implementations. ($\nu$ is w.r.t. the *per-step* $\sigma$.)

When $\sigma = 0$ the sums degenerate; fall back to finite differences on the lattice:
$$\Delta \approx \frac{V(S+u) - V(S-d)}{u+d}, \qquad \Gamma \approx \frac{V(S+u) - 2V(S) + V(S-d)}{((u+d)/2)^2}$$

### 4.2 Delta is NOT bounded by 1 — warning
Vanilla-call intuition ($\Delta \in [0,1]$) **does not apply to binaries**. Binary delta is a density-like quantity: a single dominant mixture component gives $\Delta_{\max} \approx \phi(0)/(\sqrt{T}\sigma) \approx 0.40/(\sqrt{T}\sigma)$, which **diverges as expiry approaches** for near-the-money options. Practical consequence: fully delta-hedging a near-expiry ATM binary requires enormous, rapidly-flipping underlying positions — the classic unhedgeable regime for digitals. Prefer: cap hedge size, cut quote size, and widen spreads there instead of chasing the hedge.

### 4.3 Gamma sign structure
$V(S)$ is sigmoid-shaped ⇒ $\Gamma > 0$ below the distribution center (call OTM side), $\Gamma < 0$ above (call ITM side), crossing zero near the strike-centered inflection. Magnitudes explode near expiry — same regime as §4.2.

### 4.4 Theta — exact in discrete time
$$\Theta := V(S, T-1) - V(S, T)$$
This is the **exact** one-step value decay, not an approximation (time is discrete here). Signs: ITM binary drifts toward 1 ($\Theta > 0$ for ITM call), OTM drifts toward 0 ($\Theta < 0$), $\Theta \approx 0$ at-the-money.

### 4.5 Vega direction
Larger $\sigma$ pulls every component $\Phi(z_{n_u})$ monotonically toward $\Phi(0) = \tfrac12$, so $V$ is pulled toward 0.5: **ITM binaries lose value, OTM binaries gain** — $\nu$ changes sign at-the-money. Delta hedging leaves vega and model-estimation risk unhedged.

### 4.6 Delta Hedging Mechanics
Hedge the **netted portfolio delta per underlying** ($\sum_i Q_i \Delta_i$ over all options on that underlying), not per-fill — netting reduces churn. A long binary call is hedged with **short** underlying, and vice versa.
Caveats:
- Whether underlyings are directly tradeable in 2026 is `UNKNOWN — verify against live prompt` (2025 exposed `buy_underlying`/`sell_underlying`; a "Fed funds rate" underlying may plausibly not be tradeable).
- Per-step hedging error $\approx \tfrac12 \Gamma \cdot \text{Var}[\Delta S]$ — grows exactly where §4.2 warns.
- Do **not** copy Luthra's near-expiry hacks (e.g., `return 1` for Gamma when $T < 3$): with the analytic forms above, Greeks are well-defined for all $T \geq 1$; at $T = 0$ the option is settled and all Greeks are 0.

---

## §5 — MARKET MAKING AND INVENTORY

### 5.1 Three Distinct Concepts (keep separate)

**Inventory skew**: Shift the quote midpoint away from fair value against your inventory $Q$ (Avellaneda–Stoikov-style reservation price; A-S is derived for GBM + exponential fill intensities, so treat this as a structured heuristic here, not an optimum):
$$m = V - \gamma_{\text{risk}} \cdot Q \cdot \text{Var}_h$$
where $\text{Var}_h$ = variance of the option's value change over the expected holding horizon: one-step $\text{Var}[\Delta V]$ (§5.4) if positions turn over fast, terminal $V(1-V)$ if positions ride to expiry.

**Risk-based spread widening**: Widen the half-spread $w$ as a function of option risk (Gamma, Theta, time to expiry), independent of inventory.
$$w = f(\Gamma, \Theta, \sigma, T)$$
From Luthra (2025): $w \propto \sqrt{\Gamma^2 \sigma^2 T + \Theta^2 T}$ (verify appropriateness for binary options).

**Competitive shading**: Tighten or widen quotes based on inferred competitor behavior or observed flow — a game-theoretic adjustment, not a risk adjustment.

### 5.2 Quoted Bid and Ask
Binary prices live in $[0, 1]$; clamp within it and preserve ordering (tick = minimum price increment, `UNKNOWN — verify`):
$$b = \text{clip}(m - w,\ 0,\ 1 - \text{tick}) \qquad a = \text{clip}(m + w,\ b + \text{tick},\ 1)$$
Do not use vanilla-style floors like "ask ≥ 0.01" — for a binary with $V = 0.002$ a correct ask can legitimately sit below 0.01. The economically binding constraints are $b < V < a$ (quote around your own fair value) and the $[0,1]$ bounds.

### 5.3 Spread Formula for Binary Options
Luthra's $\sqrt{\Gamma^2\sigma^2 T + \Theta^2 T}$ was a vanilla-option heuristic. For binaries, candidate half-spread components (combine; calibrate by experiment):
1. **Terminal risk**: $w_1 = \gamma_{\text{risk}}\sqrt{V(1-V)}$ — Bernoulli payoff std; appropriate if inventory rides to expiry.
2. **One-step risk**: $w_2 = \gamma_{\text{risk}}\sqrt{\text{Var}[\Delta V]}$ (§5.4) — appropriate if inventory is flattened quickly; automatically explodes in the near-expiry ATM danger zone (§4.2), which is desired behavior.
3. **Estimation-risk floor**: $w \geq \kappa_{\text{SE}} \cdot \text{SE}(\hat V)$ (§5.8) — never quote tighter than your own uncertainty about fair value.
All **proposed, not validated** — calibrate $\gamma_{\text{risk}}$, $\kappa_{\text{SE}}$ in the simulator.

### 5.4 Inventory Risk for Binary Options — covariance matters
A position of $Q$ units of one binary has terminal variance $Q^2 V(1-V)$. But the naive portfolio sum $\sum_i Q_i^2 V_i(1-V_i)$ **misstates risk**: options on the *same underlying* are functionally dependent through $S_T$.
- Two binary calls, $K_1 \le K_2$: $\text{Cov} = V(K_2)\,\bigl(1 - V(K_1)\bigr) > 0$.
- General same-underlying pairs: $\text{Cov}_{ij} = E[g_i(S_T)\,g_j(S_T)] - V_i V_j$, computable directly from the terminal distribution (§3.3).
- Portfolio variance per underlying: $\mathbf{Q}^\top \Sigma\, \mathbf{Q}$ with $\Sigma$ from pairwise covariances; cross-underlying blocks require the joint distribution (§6).
- **Better than variance**: the aggregate payoff on one underlying is a piecewise-constant function of $S_T$ with breakpoints at the held strikes — its full exact distribution (and exact worst case, §5.7) is cheap to compute. Prefer it when position counts are modest.

**One-step value variance** $\text{Var}[\Delta V]$: enumerate the two branch moves and integrate the Gaussian noise by short quadrature. Unit-test via the tower property: $E_t[V_{t+1}] = V_t$ must hold exactly — fair value is a martingale; any violation is a pricer bug (§8.6).

### 5.5 Adverse Selection Defense
Observe trade flow direction: if many buys come in at your ask, counterparties may have an information edge. Two responses:
1. Widen spread
2. Shift midpoint upward (reduce bid-side aggressiveness)
From transcript: "adapt your behavior based on information you get from your counterparties." This is explicitly expected.

Principled anchor (Glosten–Milgrom): under informed flow, the zero-profit quotes are conditional expectations — $a = E[V^\ast \mid \text{buy}]$, $b = E[V^\ast \mid \text{sell}]$; the spread is the price of trading against better information. Estimate the informed share from fill imbalance / direction autocorrelation and widen accordingly; quoting inside these bounds systematically loses to informed counterparties.

### 5.6 Bankruptcy Avoidance
Hard constraint: never let portfolio value hit zero. Conservative strategies:
- Reduce position sizes as net portfolio value declines toward threshold
- Stop quoting on one side when inventory is too extreme
- Bankruptcy protection takes priority over score optimization

### 5.7 Exact Worst-Case Loss and the Bankruptcy Constraint
Options-only book on one underlying: the aggregate terminal payoff is piecewise-constant in $S_T$ with breakpoints at the held strikes. **Exact worst case** = minimum over the $\le n+1$ strike-partition intervals plus the breakpoints themselves (evaluate breakpoints under the tie convention, §2.6). Summing per-underlying minima is the unconstrained joint worst case — conservative under any correlation structure.
With an underlying hedge position the payoff becomes piecewise-*linear* and is unbounded on open-ended intervals (Gaussian noise has unbounded support above; a floor at 0 may bound below, §3.4): bound tails at a quantile (e.g., $\pm 4$ total std) and state the residual tail risk.
Operating rule: $\text{cash} + \sum_{\text{underlyings}} \text{worst-case payoff} \ge \text{safety margin} > 0$ at all times; shrink quote sizes as margin tightens.

### 5.8 Estimation Risk — never quote tighter than you know
$\hat V$ is computed from parameters estimated off finite historical data; it carries standard error. Delta-method:
$$\text{SE}(\hat V) \approx \sqrt{\textstyle\sum_k \left(\partial V / \partial \theta_k\right)^2 \text{Var}(\hat\theta_k)}, \qquad \theta = (p, u, d, \sigma, \text{corr})$$
Quoting a half-spread below $\text{SE}(\hat V)$ invites systematic pick-off by better-calibrated opponents (winner's curse). Floor: $w \ge \kappa_{\text{SE}} \cdot \text{SE}(\hat V)$, $\kappa_{\text{SE}} \approx 1\text{–2}$.

**Winner's-curse magnitude (Milgrom–Weber 1982 applied to RFQ routing)**: with $N$ quoters holding independent errors $\varepsilon_i \sim N(0,\sigma_\varepsilon^2)$, the RFQ routes to the most optimistic, so $E[\varepsilon \mid \text{we won}] \approx \sigma_\varepsilon E[\max_N Z]$ with $E[\max_N Z] =$ 0.56 (N=2), 0.85 (N=3), 1.03 (N=4), 1.16 (N=5). Half-width must exceed $\approx \sigma_\varepsilon$ *before any profit*. Measured $\sigma_\varepsilon \approx 0.07\text{–}0.09$ ATM at 18-day warm-ups → this is why every sub-$\sigma_\varepsilon$ tightening experiment lost.

**$\sigma_\varepsilon$ estimator built and calibrated (Component 2, `_sigma_epsilon` in Market_Maker.py)** — delta-method version FAILED calibration outright (std(z)=129: local linearization breaks down when 18-day parameter uncertainty is large, not small); replaced with sampling from the estimator's own sampling distribution (12 draws/option, deterministic per option, drift–beta covariance preserved). Coverage, **replicated on a held-out seed range disjoint from the one that first characterized it** (90000–90149 vs original 4242–4391 — `python test_sigma_holdout_and_draws.py`):
| | P(\|z\|>1) | P(\|z\|>2) | P(\|z\|>3) |
|---|---|---|---|
| Gaussian target | 0.317 | 0.046 | 0.003 |
| Original seeds | 0.158 | 0.052 | 0.027 |
| **Held-out seeds** | **0.145** | **0.036** | **0.016** |
σ is conservative in the bulk on both sets; worst deep-OTM outliers are sub-tick (absolute error 0.008–0.039). `std(z)` is NOT a usable summary (139 on the original set, 1.2–2.1 on held-out — outlier-dominated, driven by rare small-sample-variance draws); coverage and bucketed absolute error are the stable metrics. **Draw-count sensitivity**: 12 vs 50 vs 100 draws → max coverage drift 0.012 (bulk metrics stable; only the discredited `std(z)`-type tail statistic is MC-noisy at 12 draws). **Keeping 12 draws.** THEO sanity: $\sigma_\varepsilon = 0$ exactly under true parameters (verified), so it cannot contaminate the THEO test.

**`w \ne k\cdot\sigma_\varepsilon` for a single scalar $k$ derived from mean(\sigma)/mean(|error|) — this was a conflation, retracted.** That ratio ($\approx 2$, i.e. mean $|\text{error}| \approx 0.5\sigma_\varepsilon$) describes how conservative $\sigma_\varepsilon$ is as an estimate of **unconditional** pricing error. It says **nothing** about the auction-selection effect above, which requires $N$ (itself only `HYPOTHESIS`-tier, §7.2b) and is *multiplicative on top of*, not a substitute for, $\sigma_\varepsilon$'s own scale. Using $0.5\sigma_\varepsilon$ as an RFQ half-width would sit **2–5× below** the $k(N)\cdot\sigma_\varepsilon$ survival requirement — the same failure mode as v6/v7 with better-calibrated inputs. **Keep as two explicit, unmerged terms until an actual measurement of realized auction-selection bias justifies combining them** (not collected this session):
$$w_{\text{RFQ}} = \underbrace{k(\hat N)\cdot\sigma_\varepsilon}_{\text{auction survival — HYPOTHESIS, }\hat N\text{ unconfirmed}} + \text{baseline economics (existing }\lambda\text{-book)}$$
$$\text{FOK edge floor} = c\cdot\sigma_\varepsilon,\quad c\approx 1\text{–2}\ \text{(quantile substitution — no auction-selection effect; separate justification, §5.8 below)}$$
**$\sigma_\varepsilon$ remains UNWIRED from all quoting/FOK logic** pending validated $\hat N$ and an arena test of the combined formula.

**Kelly sizing for binaries (Kelly 1956; Thorp 1969, 1997)**, in units of margin locked — the exact quantity Problem_2 debits:
$$\text{buy at } c:\ f^* = \frac{p-c}{1-c}, \qquad \text{sell at } c:\ f^* = \frac{c-p}{c}$$
Under parameter uncertainty substitute a conservative quantile ($p \to \hat p \mp k\sigma_\varepsilon$; Thorp's fractional-Kelly remedy). Worked example of the v6 failure: buy at 0.99 with $\hat p = 1.00$ gives $f^* = 100\%$ of bankroll, but $\hat p - \sigma_\varepsilon = 0.93 < 0.99 \Rightarrow f^* < 0 \Rightarrow$ **do not trade**.
**Objective caveat**: Kelly maximizes log-growth over many bets; our objective is *rank at a fixed horizon*. Dubins & Savage (*How to Gamble If You Must*, 1965): to maximize $P(\text{reach target})$, bold play is optimal for subfair games, timid/proportional for superfair. We have positive edge ⇒ proportional play ⇒ Kelly is a defensible approximation, not the objective itself.

### 5.9 Quote Sizing (quantities are part of the required quote)
The transcript requires quantities with each two-sided quote. Sizing rules:
- Per-quote size ≤ (available worst-case margin, §5.7) / (worst-case loss per unit if filled).
- Shrink size with inventory concentration $|Q|$ on that underlying, and in the near-expiry ATM regime (§4.2) where hedging fails.
- Never post a size whose fill would violate the §5.7 constraint even in the worst case.

---

## §6 — JOINT DISTRIBUTION AND CORRELATION

### 6.1 Why It Matters
Even if all options are on individual underlyings, the joint distribution affects:
- Estimation of individual marginal distributions from historical returns
- Possibly the option payoffs if any instrument is a joint event

### 6.2 Estimating from Historical Returns
Given a dataset of historical returns $\{(r_{\text{fed},t}, r_{\text{ajar},t}, r_{\text{theory},t})\}$:
1. Estimate per-underlying marginals: $p, u, d, \sigma$ for each (method of moments or MLE)
2. Estimate correlation matrix $\Sigma_r$ from historical return correlations
3. For pricing: if options are on individual underlyings only, marginals suffice
4. For joint options: need full copula or multivariate Gaussian approximation

### 6.3 Correlation Structure
Transcript states negative correlation: $\text{Corr}(\text{Fed}, \text{AI valuations}) < 0$.
Treat correlation as a parameter to **estimate from data**, not hardcode.

---

## §7 — GAME THEORY / COMPETITIVE LAYER

### 7.1 Bot Opponents
Transcript: "competing in a variety of scenarios with both progressively more difficult competitors." Akuna's own "battle-tested bots" (from 2025 precedent). Opponents likely include:
- Passive wide-spread quoters (easy scenarios)
- Tight fair-value quoters (standard scenarios)
- Informed/adaptive traders (hard scenarios)

### 7.2 Adapting to Counterparties
Information in counterparty behavior:
- Fill rate: high fill rate on asks → we may be underpricing (market thinks we're cheap)
- Fill rate: high fill rate on bids → we may be overpricing
- Trade direction clustering: one-sided flow suggests informed trading; widen or skew

### 7.2b Competition count $N$ — unspecified, and the estimator rests on a HYPOTHESIS
`UNKNOWN by design`: $N$ appears nowhere in the statement and varies per test ("different competing market makers"). It cannot be known at design time or at session start.

**RFQ allocation rule: `HYPOTHESIS (strongly supported)` — no engine code exists in the workspace to verify against** (`grep` for Exchange/Engine/Matcher/Router classes returns nothing; we hold only the nine given data classes). Supported by a **size-invariance natural experiment** across runs, where our quoted size at the winning price varied 20 → 120 (6×) while the order was identical:

| Run | Event | Our size | Order | Fill | Equal-split | Pro-rata |
|---|---|---|---|---|---|---|
| 1 | sell-6 RFQ | 20 | 6 | **3** | 3.0 | 0.29 |
| 2/5 | sell-6 RFQ | 120 | 6 | **3** | 3.0 | 1.38 |
| 1 | buy-4 RFQ | 20 | 4 | **2** | 2.0 | 0.19 |
| 5 | buy-4 RFQ | 120 | 4 | **2** | 2.0 | 0.92 |

Fills are size-invariant ⇒ **pro-rata/size-weighted allocation is FALSIFIED**, as is pure time-priority (predicts 0 or all). Equal-split-among-best-price matches every observation exactly.

**Estimator, and exactly how fragile it is**: $\text{fill fraction} \approx 1/\#\{\text{MMs at our price level}\}$.
- Breaks if allocation is size-dependent (falsified for the 20–120 range, unknown beyond it).
- Degrades to unbiased-but-noisy if allocation is a random lottery among tied MMs.
- **Spillover confound (real, from the spec: "splitting up the order if necessary")**: a partial fill can equally mean "we were best but quoted less than the order size." The estimator is therefore only valid when **our quoted size ≥ order quantity** — this guard must be enforced in code before any use.

FOK share is observable too: `on_trade` reports the quantity actually received, so share $=$ received $/$ `fok_order.quantity`. **Full fill on an apparently rich FOK is a WARNING (nobody else wanted it), not a gift** — adverse-selection signal.
**Safety asymmetry**: under-correcting width (too narrow) → winner's-curse losses, permanent, compounding toward ruin (score 0). Over-correcting → opportunity cost only, floored at 0.4. **Err wide**; tighten only on evidence. This derives the widen-fast/tighten-slow rule rather than assuming it.

### 7.2c FOK allocation rule — `UNKNOWN — dangling reference`
The template comment says *"See `FokOrder` for the split rule"*, but the `FokOrder` dataclass contains only fields and validators — **no split rule is documented anywhere**. Treat the FOK split as unknown; budget for receiving the FULL requested quantity (worst case) while expecting less.
**Interface constraint**: `respond_to_fok` returns `bool` — partial acceptance is impossible (*"You cannot accept part of it"*). Kelly therefore cannot size an FOK; it can only answer "is the full quantity survivable and +EV?".

### 7.3 "Own Ideas" — What the Scoring Likely Rewards
HYPOTHESIS: The competition rewards solutions that:
1. **Correctly estimate the joint distribution from historical data** (not assume it)
2. **Adapt to opponent behavior** across scenario difficulty levels
3. **Avoid bankruptcy** across all scenarios (hard constraint)
4. **Are robust across seeds** — solutions overfit to visible test cases will fail on hidden evaluation seeds

Behavioral implication: build for generalization, not for the visible test cases.

---

## §8 — IMPLEMENTATION CONVENTIONS

### 8.1 Expected API (from Luthra 2025 — verify against live prompt)
```python
class MarketMaker(BaseMarketMaker):
    def make_market(self, option: Option) -> tuple[float, float]:
        # return (bid, ask)
        ...
    
    def on_bid_hit(self, option: Option, bid_price: float) -> None:
        # called when our bid is hit (we bought the option)
        ...
    
    def on_offer_hit(self, option: Option, offer_price: float) -> None:
        # called when our offer is hit (we sold the option)
        ...
    
    def on_step_advance(self, new_underlying_state: list[Underlying], new_option_state: list[Option]) -> None:
        # called at each time step
        ...
    
    def price_option(self, option: Option) -> float:
        # return theoretical fair value
        ...
```

Key data fields (from `Underlying` dataclass):
- `underlying.valuation` = $S_t$
- `underlying.up_move_step` = $u$
- `underlying.down_move_step` = $d$  
- `underlying.up_move_probability` = $p$
- `underlying.down_move_probability` = $q$
- `underlying.noise_std_dev` = $\sigma$

Key data fields (from `Option` dataclass):
- `option.strike` = $K$
- `option.steps_until_expiry` = $T$
- `option.option_type` (CALL or PUT — UNKNOWN if binary call/put have same enum in 2026)
- `option.underlying_id` = links to underlying

**CRITICAL UNKNOWN**: In 2026 with binary options, the `option.option_type` enum and `expiry_valuation` method will be different. In 2025, `expiry_valuation = max(S-K, 0)`. In 2026, `expiry_valuation = 1 if (S > K for call) else 0`. Do not copy 2025's `expiry_valuation` logic.

### 8.2 Rounding and Precision
- Underlying valuations are rounded to 2 decimal places (from 2025 code)
- Quantities are rounded to 2 decimal places
- Option prices: round to 4 decimal places (Luthra convention; verify)
- Bid must be strictly less than ask

### 8.3 Seeding
Do not hard-code random seeds. The evaluation environment controls randomness. Avoid any strategy that depends on a specific random seed.

### 8.4 Logging
Maintain per-scenario logs: fair value at time of quote, bid/ask quoted, fills received, inventory level, P&L. This is critical for post-hoc debugging.

### 8.5 Source-of-Truth Hierarchy
1. Live 2026 HackerRank prompt / starter code ← **highest authority**
2. Our own experimental test results
3. Official 2026 video transcript
4. Historical public submissions (Luthra 2025) — structure analogous, but payoff function differs
5. Theoretical priors

### 8.6 Mandatory Pricer Unit Tests (run before any strategy work)
1. **Parity**: $V_c(K) + V_p(K) = 1 - P(S_T = K)$ for every priced option (§2.5).
2. **Tower property / martingale**: $E_t[V_{t+1}] = V_t$ exactly. Computable in closed form via $E[\Phi(\alpha + \beta\varepsilon)] = \Phi\!\left(\alpha/\sqrt{1+\beta^2}\right)$ for $\varepsilon \sim N(0,1)$ — the one-step expectation telescopes back to the $T$-step price. Any violation is a pricing bug.
3. **Monotonicity**: $V$ non-increasing in $K$ (calls); $\Delta > 0$ (calls); $V \to \mathbb{1}[S_t > K]$ as $T \to 0$.
4. **Greeks consistency**: analytic $\Delta, \Gamma$ (§4.1) match finite differences; identity $\nu = T\sigma\Gamma$ holds.
5. **Boundary**: prices always in $[0,1]$; $\sigma = 0$ path produces no NaN (§2.3, §2.6).

---

## §9 — AkunaTest (mahmah2/AkunaTest) — VERDICT
- C# code, 7 years old, 3 stars, 1 contributor, last commit 7 years ago
- Description: "Source code of Akuna Trading coding challenge" — a standard OA (order book management)
- **Not the virtual quant challenge**. Different format, different language, different era
- **Evidentiary weight: zero** for 2026 mechanics
- Safe to discard for our purposes

---

## §10 — QUICK REFERENCE: KEY FORMULAS

| Formula | Expression |
|---------|-----------|
| Binary call fair value | $V = \sum_{n_u=0}^{T} \binom{T}{n_u} p^{n_u} q^{T-n_u} \cdot \Phi\!\left(\frac{S_T^{(n_u)}-K}{\sqrt{T}\sigma}\right)$ |
| Terminal price node | $S_T^{(n_u)} = S_t + n_u u - (T-n_u)d$ |
| Put-call parity (binary) | $V_{\text{call}} + V_{\text{put}} = 1 - P(S_T = K)$ |
| Delta (analytic, $\sigma>0$) | $\Delta = \frac{1}{\sqrt{T}\sigma}\sum w_{n_u}\phi(z_{n_u})$ — **unbounded** near expiry ATM |
| Gamma (analytic, $\sigma>0$) | $\Gamma = -\frac{1}{T\sigma^2}\sum w_{n_u} z_{n_u}\phi(z_{n_u})$ |
| Vega identity | $\nu = T\sigma\Gamma$ |
| Theta (exact, discrete) | $\Theta = V(S, T-1) - V(S, T)$ |
| Drift-free condition | $p \cdot u = q \cdot d =: c$ |
| Per-step / terminal variance | $\text{Var}[X] = c(u+d)$; $\ \text{Var}[S_T] = T(c(u+d) + \sigma^2)$ |
| Payoff variance (single binary) | $V(1-V)$ |
| Same-underlying call-pair covariance ($K_1\le K_2$) | $\text{Cov} = V(K_2)(1 - V(K_1))$ |
| Baseline half-spread | $w = \max\left(\gamma_{\text{risk}}\sqrt{V(1-V)},\ \kappa_{\text{SE}}\,\text{SE}(\hat V)\right)$ |
| Tower-property test | $E_t[V_{t+1}] = V_t$ |
