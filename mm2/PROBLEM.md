# PROBLEM.md — the competition stated formally, and what follows from it

*Written after 16 grader submissions, once the mechanism was understood well enough
to state precisely. Every empirical constant cited here is measured, with the
producing script named. Companion documents: [GROUND_TRUTH.md](GROUND_TRUTH.md)
(rules, sourced verbatim), [SOLUTION.md](SOLUTION.md) (what we built),
[MEMORY.md](../MEMORY.md) (chronological evidence log).*

---

## 1. The game

A session $s$ is a tuple $(C_s,\ \mathcal O_s,\ T_s,\ \theta_s,\ \mathcal F_s)$:

| symbol | meaning | what we know |
|---|---|---|
| $C_s$ | starting capital | $\in\{10,20,40\}$, printed |
| $\mathcal O_s$ | competing market makers | printed after the fact; $n_s=\lvert\mathcal O_s\rvert\in\{1,2,3\}$ |
| $T_s$ | trading days | $\approx 20\text{–}25$ |
| $\theta_s$ | true market parameters | **hidden**; a warm-up history $H_s$ (~18 days) is given |
| $\mathcal F_s$ | customer order flow | **hidden**; observed only as it arrives |

**Underlyings.** $\theta_s$ parameterises a known generator: FED is a mean-reverting
random walk on the $0.25$ grid; AJR/THR are lognormal with a shared sector shock and
a common rate loading. Given $\theta$, prices are computable in closed form — this
part of the problem is *solved* (grader THEO error $0.0000$).

**Instruments.** Binary options paying $\mathbb 1[\sum_i w_i V_i^{(T)} \ge K]$.

**Actions.** Two channels, both customer-originated — market makers never trade
each other:

- **RFQ.** A quote $(b, q_b, a, q_a)$ is submitted *before* the direction is revealed.
  The exchange routes to the best price and splits ties equally, spilling to the
  next price level when size is exhausted. Our fill is
  $f = \min(q_{\text{side}},\ \text{share})$, where share depends on
  **competitors' quotes, which are never observed.**
- **FOK.** A take-it-or-leave-it $(\omega, \pi, Q, d)$; we accept or reject in full.
  Accepting is **non-rival**: multiple acceptors split, so declining does not deny
  the trade to anyone else.

**Solvency.** Each trade immediately locks its maximum loss ($q\pi$ to buy,
$q(1-\pi)$ to sell). Expiry credits are added at end of day, *then* solvency is
checked. Negative cash ⇒ bankrupt, session ends.

## 2. The objective — and why it is not expected PnL

Let $\Pi_s$ be our session PnL and $\Pi_{s,j}$ opponent $j$'s. The grader pays

$$
\text{score}_s=\begin{cases}
0 & \text{if bankrupt}\\[2pt]
0.4+\dfrac{0.6}{n_s}\bigl\lvert\{\,j\in\mathcal O_s:\Pi_s>\Pi_{s,j}\,\}\bigr\rvert & \text{otherwise}
\end{cases}
$$

and the total is $4+\sum_{s=1}^{16}\text{score}_s$ (the $4$ covers the pricing test
and three verbose tests). Taking expectations and writing $\rho_s$ for the
probability of staying solvent:

$$
\boxed{\ \mathbb E[\text{score}_s]=\rho_s\left[0.4+\frac{0.6}{n_s}\sum_{j\in\mathcal O_s}\mathbb P\bigl(\Pi_s>\Pi_{s,j}\ \big\vert\ \text{solvent}\bigr)\right]}
$$

**The objective is a sum of pairwise win probabilities, not expected profit.** Four
consequences follow immediately, and all four are confirmed in our logs:

1. **Margin of victory is worth exactly zero.** $\mathbb P(\Pi_s>\Pi_{s,j})$ ignores
   the size of the win. *Confirmed:* a session won by $6.7\times$ the best opponent
   scored exactly $1.00$.
2. **The weakest opponent is worth as much as the strongest.** Each $j$ contributes
   $0.6/n_s$ regardless of strength. Effort should target the *nearest* rival, never
   the leader.
3. **Variance is directional.** For roughly symmetric PnL distributions,
   $\partial\,\mathbb P(\Pi_s>\Pi_{s,j})/\partial\,\mathrm{Var}(\Pi_s)$ is **positive
   when $\mathbb E[\Pi_s]<\mathbb E[\Pi_{s,j}]$** and negative when ahead. Risk is
   therefore *good in sessions we are losing and bad in sessions we are winning* —
   the exact opposite of a PnL-maximising instinct.
4. **Ruin is uniquely catastrophic**: it forfeits the whole $0.4$ survival floor,
   which across 16 sessions is $6.4$ of the 20 available points.

Point 3 is the single most under-exploited fact in this problem, and §5 explains
why it has resisted exploitation.

## 3. Information structure

At the moment of any decision we observe:

- **Observable:** all underlying values to date; the warm-up $H_s$; every order that
  arrives (its option, price, size, side, counterparty id) **whether or not we
  trade it**; our own fills and settlements; our own cash and locks.
- **Never observable:** $\theta_s$; competitors' quotes; competitors' PnL (hence our
  own rank); the flow's future; whether a given order was informed.

The critical asymmetry: **we see order prices for free, but we only see payoffs by
taking risk.** Section 4 shows these two channels differ in information content by
about two orders of magnitude — which turns out to explain every failed adaptive
mechanism we built.

## 4. The information limit on adaptation

*(computed in [information_budget.py](information_budget.py); session size from the
verbose-log counts in MEMORY E55: ≈ 1 RFQ + 1 FOK per day over ≈ 22 days)*

**Channel A — realised PnL / markouts.** A settled binary at theo $p$ has outcome
standard deviation $\sqrt{p(1-p)}$, while our per-trade edge is the quoted
half-width $\approx 0.04$. The per-trade effect size is
$\delta = 0.04/\sqrt{p(1-p)}$, so detecting it at 95%/80% needs
$n \approx (2.49/\delta)^2$ settled trades:

| theo | per-trade sd | $\delta$ | fills needed | fills available | shortfall |
|---|---|---|---|---|---|
| 0.50 | 0.500 | 0.080 | 965 | ~15 | **64×** |
| 0.20 | 0.400 | 0.100 | 618 | ~15 | **41×** |
| 0.05 | 0.218 | 0.184 | 183 | ~15 | **12×** |

**Within a session, our own edge quality is unmeasurable by one to two orders of
magnitude.** This is an information limit, not a tuning failure — and it retroactively
explains why every detector we built on this channel false-fired at 9–24% in benign
sessions (pooled-markout z: 9–15%; realised-drawdown brake: 3.6–23.7%). They were
reading noise, and no threshold could have fixed them.

**Channel B — observed order prices.** Each arriving order yields
$\pi - \hat V$ directly, with *no payoff noise*; the only dispersion is across
orders. Measured on the five fully-logged orders: mean $+5.8$¢, dispersion sd
$3.8$¢. Hence after $n$ observed orders the flow's mean aggression is resolved to
$2.49\cdot 0.038/\sqrt n$:

| observed orders | resolution |
|---|---|
| 10 | ±3.0¢ |
| 20 | ±2.1¢ |
| 40 | ±1.5¢ |

With ~22 orders per session we resolve mean flow aggression to about **±2¢** —
finer than our own 3.5¢ base edge, and far finer than the gap between a donating
flow ($+10$¢) and a toxic one ($-5$¢).

> **Result.** In-session adaptation is *not* impossible. It is impossible **on the
> realised-PnL channel** and feasible **on the observed-order-price channel**. Every
> adaptive mechanism we designed and rejected used the wrong channel.

## 5. Where the remaining points actually are

*(derived in [where_the_points_are.py](where_the_points_are.py))*

The deficit is not diffuse. **Every test containing the Stalemate Quoter is a test
we fail to win; every test without it scores 1.0.** And Stalemate's PnL is an
integer in every log ever produced — \$43, \$30, \$5, \$2, \$0 — because it buys at
0.00 and sells at 1.00, so a binary settling 0 or 1 makes its profit a literal
*count of free lots*.

Those lots are ours, donated. Our displayed bid size is $\lfloor\text{budget}/\text{bid}\rfloor$; at
theo $0.50$ on a \$10 book that is $\lfloor 2.50/0.46\rfloor = \mathbf 5$ lots. Orders run to
12–200 lots, so everything above 5 spills to the 0.00 bid. TC5's "Stalemate:
\$30.0" is 30 such lots.

**This is a capacity constraint, not a pricing or width error** — which is exactly
why four width experiments failed and why the only two changes that ever gained
live (capacity fix +1.6, free-roll +0.5) were both size-increasing.

The governing asymmetry: **on a bid, margin per lot *is* the price.** A lower bid
buys more lots with the same margin *and* carries more edge per lot — both move the
right way simultaneously:

| our bid | lots affordable | edge/lot | E[profit] on a 35-lot order | worst case |
|---|---|---|---|---|
| 0.46 | 5 | 0.04 | \$0.20 | −\$2.30 |
| 0.05 | 50 | 0.45 | **\$15.75** | **−\$1.75** |

Bidding 0.05 earns 79× more *and risks less* — provided nobody outbids us. That
proviso is the whole problem, and it depends on the unobservable roster.

## 5a. A negative result: the passive signal does not work

The obvious candidate was the **capped event** $C=\mathbb 1[\text{fill}=\text{displayed}]$, which is
observed exactly and needs no payoff. It fails: at theo $0.50$ we outbid Stalemate
(0.000), FW0.25 (0.375) *and* FW0.10 (0.450), so $\mathbb P(C=1)\approx 1$ in all three
regimes. The signal cannot distinguish the one roster where widening is right from
two where it is ruinous. **Passive observation is insufficient — not for lack of
data, but for lack of contrast.**

## 5b. An active probe — proposed, implemented, and FALSIFIED

*(derived in [two_designs.py](two_designs.py) and [design_c.py](design_c.py);
killed by [check_design_c.py](check_design_c.py))*

The proposal was to create contrast deliberately: bid 0.45 once at high theo and
record fill/no-fill. Since no fixed-width archetype ever bids below $\text{theo}-0.125$,
a fill *appeared* to prove the field bids nothing — and placed deep-ITM, where our
displayed size is 2 lots, it costs only \$0.07 for information that transfers to
every theo (cross-learning, §8.2).

**It does not work, and the reason is the spillover rule itself.** A fill at a deep
price does **not** imply nobody bid higher. It implies the field's *displayed size*
at better prices was exhausted — and the residual then falls to whatever is
underneath, which is exactly the mechanism §5 is about. Any large order produces a
deep fill regardless of who is quoting.

Measured over 60 sessions per roster, with the trigger implemented in the live bot:

| roster | armed | should arm |
|---|---|---|
| TC5 stale | 27/60 | yes |
| TC7 **fw25 only** | **7/60** | **no — false positive** |
| TC9 **fw10 + fw25** | **4/60** | **no — false positive** |

Sweeping in TC7 or TC9 would forfeit tests we currently hold at 1.00.

The discrimination per probe is $\mathbb P(\text{fill}\mid\text{stale})\approx0.45$ versus
$\mathbb P(\text{fill}\mid\text{fw25})\approx0.12$. Separating those needs on the order of
8–10 probes at ≈\$0.10 each — roughly \$0.80, which exceeds the entire margin of most
tests. **So this collapses into §4 again: an information limit, on the very channel
this section claimed was clean.** The change was reverted before submission.

## 6. Solution approaches, ranked by feasibility

| approach | status | verdict |
|---|---|---|
| Exact pricing from estimated $\theta$ | **done** — THEO error 0.0000 | solved |
| Solvency by construction (lock = max loss, budgeted sizing) | **done** — 0 bankruptcies in 1,440 out-of-domain sessions | solved |
| Structural fixes (capacity, free rolls, sign bugs) | **done** — the only family that ever gained live (+1.6, +0.5) | the winning family |
| Width / selectivity tuning | falsified in **both** directions live | closed |
| Adaptation on realised PnL | **provably impossible** (§4A, 12–64× shortfall) | closed |
| Adaptation on passive fill/capped rate | **falsified** (§5a — no contrast between regimes) | closed |
| Adaptation on an active deep probe | **falsified** (§5b — spillover fills deep bids regardless of the field) | closed |
| Offline policy search | arena inverts the one ranking we can check | closed |
| **Penny-inside** at the 0.00/1.00 tie (design B) | ~neutral by arithmetic: at 0.99 a \$10 book affords ~250 lots versus 500 free at 1.00, so the margin cost cancels the tie-split gain | closed |

## 7. The honest position

Pricing and solvency are solved. Width is at a two-sided local optimum that four
live experiments failed to improve, and §5 explains why: **width was never the
binding constraint — margin-limited displayed size was.** The residual we cannot
afford to quote for is donated at 0.00/1.00 to an opponent whose margin cost is
zero, and that donation is the gap between 0.4 and 1.0 in every Stalemate test.

The answer to "is adaptation possible on data this thin" is now, after building and
testing each candidate:

- on **realised PnL** — no, by a factor of 12–64, provably;
- on **passive fill observation** — no, for want of contrast rather than data;
- on an **active deep probe** — no. It looked clean on paper and cost only \$0.07,
  but spillover means a deep fill measures *exhausted size*, not an empty field. It
  false-fired on 7/60 TC7 sessions and 4/60 TC9 sessions — both tests we hold at
  1.00. Separating the regimes would take ~\$0.80 of probing, more than the margin
  of most tests.

So all three adaptation channels are closed, each for a different and now-measured
reason. What remains is §5's economics without any detector attached: on a bid,
margin per lot *is* the price, so a deeper bid buys more lots and more edge per lot.
That is a real and unexploited asymmetry. It is not currently actionable, because
every way we have found to decide *when* to use it requires information the session
does not contain.

---

## 8. Prior art

None of the three subproblems is novel. Each has a named literature, and in two
cases the literature had already named the exact structure we rediscovered.

### 8.1 The objective — *contest theory*, and it is our game almost exactly

**Seel & Strack, "Gambling in contests", J. Econ. Theory 148(5) 2033–2048 (2013).**
$n$ players each privately observe a Brownian motion with drift, **absorbed at
zero** (a player whose process hits zero must stop); the player with the highest
stopped value wins; each maximises *probability of winning*. Private observation =
we never see rivals' PnL. Absorption at zero = bankruptcy. Rank objective = §2.

Its answer is the formal version of §2.3, and sharper than anything we derived: the
symmetric equilibrium is not a target *level* but a target **distribution** — in the
two-player contest, the stopped value is **uniform on $[0,2x_0]$**. Maximising a win
probability means deliberately engineering terminal dispersion, not expected value.

Follow-ups that matter for our variant:
- **Nutz & Zhang, "Reward Design in Risk-Taking Contests", SIAM J. Fin. Math.
  (arXiv 2102.03417)** — **rank-dependent** rewards rather than winner-take-all.
  Ours is rank-dependent ($0.4+0.6\cdot$fraction beaten), so this is the right variant.
- **Feng & Hobson, Ann. Appl. Probab. 26(1) 186–215 (2016), arXiv 1405.7801** —
  heterogeneous (random) initial values; we face \$10/\$20/\$40 books.
- **Feng & Hobson, arXiv 1301.0719** — Lagrangian re-derivation of Seel–Strack.
- **Browne, "Reaching goals by a deadline: digital options and continuous-time
  active portfolio management"** (Columbia GSB 96-16) — maximise $\mathbb P(\text{beat a
  stochastic benchmark})$ by a deadline.

> **Caveat that limits the transfer.** Seel–Strack solves for the *symmetric Nash
> equilibrium among rational players*. Our opponents are **fixed, non-strategic
> bots**. We therefore do not want the equilibrium — we want the **best response** to
> a known opponent distribution, which is a strictly easier problem. What carries
> over is the *form* of the answer (choose a terminal distribution, not a mean),
> not the uniform-on-$[0,2x_0]$ prescription itself.

### 8.2 The learning problem — *censored-feedback auction learning*

**Han, Zhou & Weissman, "Optimal No-regret Learning in Repeated First-price
Auctions", Operations Research (arXiv 2003.09795).** Their setting is ours
verbatim: a bidder who observes only whether she won faces **censored feedback** —
win, and you never learn the rival's bid. They achieve $\widetilde O(\sqrt T)$ regret by
exploiting two structural properties, and **both are things we derived by hand**:

1. **Graph feedback across actions.** Bids are monotone, so one probe at depth $d$
   resolves *every* depth simultaneously — lose at $d$ and you would have lost at
   every deeper bid. Our probe is not one bit of information; it is a half-line.
2. **Cross-learning across contexts.** An outcome observed at one private value is
   informative at all others. This is precisely what licenses §5b's "probe at theo
   0.90 (\$0.07), exploit at theo 0.20" — the transfer is the *named mechanism*, not
   an assumption we smuggled in.

See also **Huang & Huang, arXiv 2502.04678**, on cross-learning contextual bandits
with graphical feedback, which tightens the bounds for exactly this structure.

### 8.3 The constraint — *budgeted bidding* and *OTC/RFQ market making*

- **Balseiro, Lu & Mirrokni, "The Best of Many Worlds: Dual Mirror Descent for
  Online Allocation Problems" (arXiv 2011.10124).** Maintain a **Lagrangian dual
  multiplier per scarce resource**, updated by online mirror descent, and act as if
  the resource costs $\lambda$ per unit. Asymptotically optimal under stochastic *and*
  adversarial input. **Our `CAPITAL_WIDEN * utilization` term is a hand-rolled,
  hand-tuned version of exactly this dual variable** — the principled replacement is
  to *learn* $\lambda$ online instead of fixing it at 0.25.
- **Immorlica, Sankararaman, Schapire & Slivkins, "Adversarial Bandits with
  Knapsacks", JACM (arXiv 1811.11881)** — bandits under budget/supply constraints.
- **Bergault & Guéant, "Size matters for OTC market makers" (arXiv 1907.01225)** —
  RFQ making where the dealer quotes **different prices for different sizes**; the
  price–size schedule is our §5 lever.
- **Barzykin, "Win-score promotion gates in aggregator-routed RFQ markets"
  (arXiv 2603.10569)** — dealer chooses a **size-ladder of bid/ask offsets**, with an
  explicit mapping from optimal *win probabilities* to optimal offsets.
- **Feil & Nendel, "Optimal Market Making in Prediction Markets"
  (arXiv 2607.17991)** — states plainly that **binary settlement makes the control
  problem fundamentally different from classical market making**. Useful negative
  result: it confirms Avellaneda–Stoikov cannot simply be lifted onto our instrument.
- Background: **Guéant, Lehalle & Fernandez-Tapia (arXiv 1105.3115)**; **Guéant,
  "Optimal market making" (arXiv 1605.01862)**; **Barzykin, Bergault, Guéant &
  Lemmel, "Optimal Quoting under Adverse Selection and Price Reading"
  (arXiv 2508.20225)**.

### 8.4 What the literature actually buys us

| our finding | prior art | status |
|---|---|---|
| variance is directional (§2.3) | Seel–Strack; Nutz–Zhang | **solved, and sharper** — target a distribution |
| probe resolves all depths at once | graph feedback across actions | **named mechanism**, not a heuristic |
| regime learned at high theo transfers to low | cross-learning across contexts | **named mechanism**, licenses design C |
| `CAPITAL_WIDEN × utilization` | dual mirror descent | **ours is the crude version**; λ should be learned |
| binary payoff breaks classical MM | Feil–Nendel | confirms we could not have reused A–S |

The honest read: the literature validates the *structure* of design C and supplies a
principled replacement for one hand-tuned constant, but it does not hand us a drop-in
policy. Every result above is asymptotic ($\widetilde O(\sqrt T)$ regret, equilibrium
distributions) and our $T$ is **22**. Section 4's information budget is what actually
binds, and no amount of regret-optimality changes it.
