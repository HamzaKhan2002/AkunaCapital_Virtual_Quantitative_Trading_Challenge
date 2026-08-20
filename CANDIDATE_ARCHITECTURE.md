# Candidate Solution Architecture — Akuna 2026 MarketMaker

*Status: v9 candidate (v5 + one validated change). Every claim carries its evidence tier.*
*Score trajectory: 13.2 → 13.8 → 14.0 → ~13.9 → **15.2 (v5)** → 13.6 (v6, reverted) → v9 pending.*

---

## 0. Gap Diagnosis verdict (mandated question: why does v5 lose?)

Matched-seed oracle/ablation experiments (`diagnose_gap.py`, `experiment_lambda_ceiling.py`, 800+800 sessions):

| Candidate cause | Test | Result | Verdict |
|---|---|---|---|
| Parameter estimation | v5 policy + TRUE MarketParameters | score 0.8680 → 0.8680, **+0.0000** | `REJECTED` as bottleneck |
| Quote width (λ) | λ sweep 0.60–0.94 under oracle params, hardest world | flat 0.841–0.850 | `REJECTED` as bottleneck |
| FOK policy | per-fill attribution: FOK fills carry **0.06–0.18/lot illusory edge** (estimated edge that does not exist under true values); RFQ illusory edge ≈ 0.00–0.05 | fixed by σ-bound (below), **SIG+ pooled** | `CONFIRMED` leak, now patched |
| Residual | after all of the above: ~0.85 ceiling in lean-flow worlds vs tight pricers | rank decided by Bernoulli outcomes of 13–15 fills/session | `HYPOTHESIS`: irreducible rank variance in-world |

**Answer to the 4.4-point question**: within our best world-reconstruction, the gap is **not estimation, not width tuning** — it was partly the FOK module (patched), and the remainder is rank variance in low-fill sessions plus the possibility that the grader's hard tests are more winnable than our reconstructions (`UNKNOWN`). A 19.6 performance is consistent with either a more winnable real test set or fixed-seed fingerprinting (`UNKNOWN`, cannot distinguish from outside).

**Recommendation (mandated)**: keep the v5 policy family; **replace no module wholesale**; ship the one validated FOK patch; do not spend remaining time on width/estimation tuning — the experiments bound those gains at ≈ 0.

---

## 1. Final proposed policy (v9), by module

| Module | Policy | Change vs v5 |
|---|---|---|
| **Pricing** | Exact rate-grid DP × conditional bivariate-lognormal; closed-form zero-strike spreads; 241-node quadrature general 2-leg | none (THEO max_error 0.0000) |
| **Estimation** | Raw OLS on 18-day warm-up (rate tilt line-fit, log-return regressions, residual covariance) + standard errors | none shipping (shrinkage flag exists, OFF) |
| **Uncertainty** | `_sigma_epsilon`: 12-draw sampling of estimator's sampling distribution; held-out calibrated | new *measurement*, consumed only by FOK gate |
| **RFQ quoting** | λ-book: bid = λ·V̂, offer = 1−λ(1−V̂), λ=0.72 neutral / 0.35 toxic / rung-laddered 0.15→0.03 dumb; inventory skew in λ-space; solvency degrade to 0.00/1.00; lock-scaled sizes | none |
| **FOK** | All v5 gates (lock cap, ratio floor, edge threshold, toxicity, inventory) **plus: edge ≥ σε required outside DUMB regime** | **the v9 change** |
| **Risk/cash** | Exact max-loss ledger mirroring Problem_2; 8% reserve; drawdown → TOXIC at −5%; per-option position caps | none |
| **Adaptation** | Junk-fill (≥8¢ through theo) regime detection; markout-based counterparty & global toxicity; flow-IQ from observed FOKs | none |

## 2. Theory per module (one line each + source)

- Pricing: companies load on the rate path only through r_T−r_0 ⇒ exact factorization (verified vs 300k-path MC of the actual `advance_step`).
- λ-book: uniform expected return per locked dollar ≈ (1−λ)/λ; incidentally error-proportional (w(V) ∝ min(V,1−V) ≈ σε(V) shape) — why it survives the winner's curse without an explicit N-term.
- σε: parameter-uncertainty propagation by sampling (delta method REJECTED — failed calibration, std(z)=129).
- FOK σ-gate: Thorp's fractional-Kelly/quantile substitution — accept only if edge exceeds our own uncertainty; gated in DUMB because uninformed crossers don't exploit estimation error (measured: raw bound SIG− in dumb world).
- Risk: lock = worst case (binary payoffs) ⇒ bankruptcy impossible while ledger ≥ 0 (0 bankruptcies in ~6,000 arena sessions).
- Scoring: E[score] = 0.4 + 0.6·mean pairwise P(win); margin of victory worthless (`CONFIRMED`, no headroom above 1.00).

## 3. Evidence per experiment (all reproducible by script)

| Experiment | Sessions | Finding |
|---|---|---|
| `experiment_shrinkage.py` / `_hard.py` | 1,200 paired | RMSE −34% in-session `CONFIRMED`; score effect ns (+0.002) → **not shipped** (fails doctrine (b)) |
| `diagnose_gap.py` | 800 | oracle params close 0.0000 of gap; FOK illusory edge 0.06–0.18/lot |
| `measure_selection_bias.py` | 360 | RFQ selection premium 0.005–0.013 (0.03–0.07×σε) ≪ Milgrom–Weber table → λ-book already covers it; **no N-term needed** |
| `experiment_fok_ablation.py` (3 seed blocks) | 1,200+2,000+2,000 | raw σ-bound `REJECTED` (SIG− dumb); **gated σ-bound `CONFIRMED`: +0.0099 pooled [+0.0034, +0.0164], SIG+ in 2 worlds, no SIG− anywhere, fresh seeds** |
| `experiment_lambda_ceiling.py` | 500 | λ sweep flat under oracle → width tuning bounded at ≈ 0 |

## 4. Remaining HYPOTHESIS / UNKNOWN register

- `HYPOTHESIS (strongly supported)`: RFQ equal-split at tied prices (size-invariance experiment falsified pro-rata & time-priority; rule unverifiable — no engine code).
- `HYPOTHESIS`: arena flow/opponent models resemble grader hard tests (calibrated to VERBOSE logs + PnL signatures only).
- `UNKNOWN`: FOK split rule (dangling template reference); score law at n≥4 and at PnL ties; grader session lengths/flow rates in SCORED tests; whether 19.6-level scores are honest or fingerprinted; Round 2 format.
- `REJECTED` this session: delta-method σε; raw (ungated) FOK σ-bound; shrinkage as score-mover (kept as flag for possible Round-2 rehabilitation); width/N winner's-curse add-on term at v5 widths.

## 5. Robustness statement

v9 is robust to: unknown opponent composition (no dependency on opponent identity or count; N-estimator never shipped); unknown FOK split (budgets for full quantity); unknown flow regime (regime detection works at 2–4 events/day, single-fill evidence); estimation error (FOK gate + λ-book width both scale with it); aggregation-rule uncertainty (uniform per-test optimization); bankruptcy (worst-case ledger, structurally solvent — never relaxed under any regime).
v9 is NOT robust to: adversaries specifically exploiting the λ-book's deterministic shape (`HYPOTHESIS` risk, unobserved so far); grader worlds far outside our reconstruction; chaos in fixed-seed per-test outcomes (±0.3/test swings remain possible on any single run).

## 6. Red-team: three most likely failure modes on hidden tests

1. **Arena-world mismatch**: the gated FOK σ-bound was validated in reconstructed worlds; if grader FOK flow is dominated by a pattern we didn't model (e.g., near-certain arbs at qty 1), the gate could refuse real money. Mitigation: gate only *adds* a filter to already-accepted FOKs; worst case is opportunity cost, bounded by v5's FOK PnL share.
2. **Chaos on the fixed seeds**: a +0.01-expected change can print −0.6 on one run (v8 lesson). Mitigation: accept the single-run draw; judge v9 by principle + arena evidence; revert only on structural evidence (bankruptcy/errors), not score noise.
3. **σε runtime**: 12 reprices per FOK accept-path call. Bounded: only on FOKs that pass all v5 gates (~1–3/day). If the grader times out, the exception wrapper defaults to rejection — safe but blunt. Pre-submission check: none possible locally beyond arena timing (ran fine).

## 7. Final validation & submission plan

1. ✅ `validate_live.py` (THEO exactness + mechanics) — ALL PASS on v9.
2. ✅ `sim_arena.py` standard archetypes — 0.985, no regressions vs v5's 0.975–0.985 band.
3. ✅ Fresh-seed confirmation of the only new mechanism (2,000 sessions, SIG+).
4. Submit v9 once. Read per-test table against Run 5's (15.2). Expected honest range: 15.0–16.5 (chaos band ± the +0.16 expected from 16 × 0.0099).
5. If v9 ≥ v5's 15.2: **stop iterating**; bank it as the final Round-1 submission; spend remaining time on Round-2 preparation (fresh-scenario robustness, not seed-fitting).
6. If v9 < 14.6 (outside chaos band): revert to exact v5 (one-line change: remove the σ-gate block), submit v5, stop.
