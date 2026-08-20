"""Calibration test for Component 2: is sigma_epsilon an honest error bar?

If well-calibrated, z = (V_hat - V_true)/sigma_eps has std dev ~ 1 across many
(parameter draw, warm-up history, option) scenarios. Too small => overconfident
(we would quote inside our own error); too large => needlessly wide quotes.
"""
import math
import random
import statistics

from Market_Maker import (
    AJARAI_UNDERLYING_ID as AJR,
    FED_FUNDS_RATE_UNDERLYING_ID as FED,
    THERIODIC_UNDERLYING_ID as THR,
    BinaryOption,
    MarketHistory,
    MarketMaker,
    OptionLeg,
    Underlying,
    _MarketModel,
    _price_with_model,
    _sigma_epsilon,
)
from sim_arena import _params

WARM_UP_DAYS = 18  # matches the grader (backed out in E7)


def build_options(vals: dict[int, float], rng: random.Random) -> list[BinaryOption]:
    out = []
    oid = 0
    for expiry in (1, 2, 3, 5, 10):
        for mult in (0.94, 0.98, 1.0, 1.02, 1.06):
            oid += 1
            out.append(BinaryOption(
                legs=(OptionLeg(underlying_id=AJR, weight=1.0),),
                option_id=oid, steps_until_expiry=expiry, strike=round(vals[AJR] * mult, 2)))
            oid += 1
            out.append(BinaryOption(
                legs=(OptionLeg(underlying_id=THR, weight=1.0),),
                option_id=oid, steps_until_expiry=expiry, strike=round(vals[THR] * mult, 2)))
        for off in (-0.5, -0.25, 0.0, 0.25, 0.5):
            oid += 1
            out.append(BinaryOption(
                legs=(OptionLeg(underlying_id=FED, weight=1.0),),
                option_id=oid, steps_until_expiry=expiry, strike=max(round(vals[FED] + off, 2), 0.0)))
        oid += 1
        ratio = vals[AJR] / max(vals[THR], 1e-9)
        out.append(BinaryOption(
            legs=(OptionLeg(underlying_id=AJR, weight=1.0),
                  OptionLeg(underlying_id=THR, weight=-round(ratio * rng.uniform(0.95, 1.05), 4))),
            option_id=oid, steps_until_expiry=expiry, strike=0.0))
    return out


def main() -> None:
    MarketMaker.TELEMETRY = False
    zs: list[float] = []
    sigmas: list[float] = []
    abs_errs: list[float] = []
    by_bucket: dict[str, list[float]] = {"deep": [], "mid": [], "atm": []}
    bucket_rows: dict[str, list[tuple[float, float, float]]] = {"deep": [], "mid": [], "atm": []}
    zero_sigma = 0

    for seed in range(150):
        rng = random.Random(4242 + seed)
        params = _params(rng)
        true_model = _MarketModel.from_parameters(params)

        random.seed(rng.randrange(1 << 30))
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
            sigma = _sigma_epsilon(est, option, vals)
            err = v_hat - v_true
            abs_errs.append(abs(err))
            sigmas.append(sigma)
            b = "atm" if 0.35 <= v_true <= 0.65 else ("mid" if 0.05 <= v_true <= 0.95 else "deep")
            if sigma < 1e-6:
                zero_sigma += 1
                continue
            z = err / sigma
            zs.append(z)
            by_bucket[b].append(z)
            bucket_rows[b].append((err, sigma, v_true))

    print(f"scenarios: {len(abs_errs)} option-prices, {len(zs)} with sigma > 0 "
          f"({zero_sigma} degenerate)")
    print(f"mean |V_hat - V_true| : {statistics.fmean(abs_errs):.4f}")
    print(f"mean sigma_eps        : {statistics.fmean(sigmas):.4f}")
    print(f"RMS error             : {math.sqrt(statistics.fmean([e * e for e in abs_errs])):.4f}")

    # std(z) is the wrong summary for a BOUNDED, heavy-tailed quantity: deep-OTM prices
    # are pinned near 0/1 so z explodes while the ABSOLUTE error stays tiny. Coverage and
    # absolute-error containment are the decision-relevant metrics for a quote-width floor.
    print("\nCOVERAGE  (fraction with |error| > k*sigma; Gaussian targets in parens)")
    for k, target in ((1.0, 0.317), (2.0, 0.046), (3.0, 0.003)):
        frac = sum(1 for z in zs if abs(z) > k) / max(len(zs), 1)
        print(f"  |z| > {k:.0f} : {frac:.3f}  (target {target:.3f})")
    az = sorted(abs(z) for z in zs)
    print(f"  median |z| : {az[len(az) // 2]:.2f}   p95 |z| : {az[int(0.95 * len(az))]:.2f}"
          f"   std(z) : {statistics.pstdev(zs):.1f} (outlier-dominated, see note)")

    print("\nABSOLUTE-ERROR CONTAINMENT BY MONEYNESS  (what actually costs money)")
    print(f"  {'bucket':<6}{'n':>6}{'mean|err|':>11}{'mean sigma':>12}{'P(err>sigma)':>14}{'P(err>2sig)':>13}")
    for name in ("atm", "mid", "deep"):
        rows = bucket_rows[name]
        if not rows:
            continue
        errs = [abs(r[0]) for r in rows]
        sgs = [r[1] for r in rows]
        p1 = sum(1 for e_, s_ in zip(errs, sgs) if e_ > s_) / len(rows)
        p2 = sum(1 for e_, s_ in zip(errs, sgs) if e_ > 2 * s_) / len(rows)
        print(f"  {name:<6}{len(rows):>6}{statistics.fmean(errs):>11.4f}"
              f"{statistics.fmean(sgs):>12.4f}{p1:>14.3f}{p2:>13.3f}")

    worst = sorted(bucket_rows["deep"], key=lambda r: abs(r[0]) / max(r[1], 1e-9), reverse=True)[:3]
    print("  worst deep outliers (err, sigma, V_true):")
    for err, sg, vt in worst:
        print(f"    err={err:+.4f}  sigma={sg:.5f}  V_true={vt:.4f}")

    print()
    print("THEO SANITY: sigma_eps must be exactly 0 when parameters are known")
    rng = random.Random(7)
    params = _params(rng)
    vals = {FED: 2.5, AJR: 500.0, THR: 600.0}
    opts = build_options(vals, rng)
    tm = _MarketModel.from_parameters(params)
    worst = max(_sigma_epsilon(tm, o, vals) for o in opts)
    print(f"  max sigma_eps under true params: {worst:.2e}  {'PASS' if worst == 0.0 else 'FAIL'}")


if __name__ == "__main__":
    main()
