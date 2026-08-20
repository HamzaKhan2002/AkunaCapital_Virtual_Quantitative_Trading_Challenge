"""Held-out recalibration (item 2) + Monte Carlo draw-count sensitivity (item 3).

Item 2: the original test_sigma_calibration.py run (E21) used seeds 4242-4391 to BOTH
observe sigma's behavior AND informally derive the "use ~0.5*sigma" scale note. That is
circular if repeated on the same seeds. This script uses a DISJOINT seed range
(90000-90149) never touched by that derivation, and reports coverage fresh.

Item 3: _sigma_epsilon now accepts n_draws; rerun the held-out set at 12/50/100 draws
and check whether tail behavior is genuine (stable) or MC noise (drifts with more draws).
"""
import math
import statistics

from Market_Maker import (
    AJARAI_UNDERLYING_ID as AJR,
    FED_FUNDS_RATE_UNDERLYING_ID as FED,
    THERIODIC_UNDERLYING_ID as THR,
    MarketHistory,
    MarketMaker,
    Underlying,
    _MarketModel,
    _price_with_model,
    _sigma_epsilon,
)
from sim_arena import _params
from test_sigma_calibration import WARM_UP_DAYS, build_options

HOLDOUT_SEED_BASE = 90_000  # disjoint from 4242-4391 used in E21
N_SEEDS = 150


def collect(draws: int):
    import random as _random

    zs, bucket_rows = [], {"deep": [], "mid": [], "atm": []}
    for seed in range(N_SEEDS):
        rng = _random.Random(HOLDOUT_SEED_BASE + seed)
        params = _params(rng)
        true_model = _MarketModel.from_parameters(params)

        _random.seed(rng.randrange(1 << 30))
        vals = {FED: 2.0, AJR: rng.uniform(200.0, 1500.0), THR: rng.uniform(200.0, 2500.0)}
        hist = {k: [v] for k, v in vals.items()}
        for _ in range(WARM_UP_DAYS):
            vals = params.advance_step(vals)
            for k in hist:
                hist[k].append(vals[k])
        history = MarketHistory(values_by_underlying_id={k: tuple(v) for k, v in hist.items()})

        underlyings = [
            Underlying(name="FED", underlying_id=FED, value=vals[FED]),
            Underlying(name="AJR", underlying_id=AJR, value=vals[AJR]),
            Underlying(name="THR", underlying_id=THR, value=vals[THR]),
        ]
        options = build_options(vals, rng)
        mm = MarketMaker(underlyings, options, 20.0)
        mm.warm_up(history)
        est = mm._model
        if est is None:
            continue

        for option in options:
            v_true = _price_with_model(true_model, option, vals)
            v_hat = _price_with_model(est, option, vals)
            sigma = _sigma_epsilon(est, option, vals, n_draws=draws)
            if sigma < 1e-6:
                continue
            err = v_hat - v_true
            z = err / sigma
            zs.append(z)
            b = "atm" if 0.35 <= v_true <= 0.65 else ("mid" if 0.05 <= v_true <= 0.95 else "deep")
            bucket_rows[b].append((err, sigma))
    return zs, bucket_rows


def report(draws: int, zs: list[float], bucket_rows: dict) -> dict:
    cov = {k: sum(1 for z in zs if abs(z) > k) / len(zs) for k in (1.0, 2.0, 3.0)}
    print(f"\n--- n_draws = {draws}  (n={len(zs)} priced scenarios) ---")
    print(f"  P(|z|>1)={cov[1.0]:.3f} (Gaussian .317)  P(|z|>2)={cov[2.0]:.3f} (.046)  "
          f"P(|z|>3)={cov[3.0]:.3f} (.003)")
    print(f"  std(z)={statistics.pstdev(zs):.1f}  median|z|={statistics.median(sorted(abs(z) for z in zs)):.3f}")
    for name in ("atm", "mid", "deep"):
        rows = bucket_rows[name]
        if not rows:
            continue
        errs = [abs(e) for e, _ in rows]
        sgs = [s for _, s in rows]
        p1 = sum(1 for e_, s_ in zip(errs, sgs) if e_ > s_) / len(rows)
        print(f"  {name:<5} mean|err|={statistics.fmean(errs):.4f}  mean sigma={statistics.fmean(sgs):.4f}"
              f"  P(err>sigma)={p1:.3f}")
    return cov


def main() -> None:
    MarketMaker.TELEMETRY = False
    print("=== HELD-OUT RECALIBRATION (seeds 90000-90149, never used to derive '0.5*sigma') ===")
    results = {}
    for draws in (12, 50, 100):
        zs, bucket_rows = collect(draws)
        results[draws] = report(draws, zs, bucket_rows)

    print("\n=== STABILITY CHECK: does coverage drift as draws increase? ===")
    print(f"{'k':>4}" + "".join(f"{'d='+str(d):>10}" for d in (12, 50, 100)))
    for k in (1.0, 2.0, 3.0):
        print(f"{k:>4.0f}" + "".join(f"{results[d][k]:>10.3f}" for d in (12, 50, 100)))
    max_drift = max(abs(results[100][k] - results[12][k]) for k in (1.0, 2.0, 3.0))
    print(f"\nmax coverage drift (12 -> 100 draws): {max_drift:.4f}")
    print("STABLE (12 draws sufficient)" if max_drift < 0.02 else "DRIFTING (12 draws is not enough)")


if __name__ == "__main__":
    main()
