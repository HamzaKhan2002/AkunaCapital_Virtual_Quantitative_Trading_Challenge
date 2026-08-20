"""Falsification test: does shrinkage actually reduce theo error on 18-day warm-ups?

Builds raw-OLS and shrunk models on the same short histories; compares pricing RMSE
vs the true-parameter model over the standard option battery.
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
    _fit_line,
    _MarketModel,
    _price_with_model,
)
from sim_arena import _params
from validate_live import BATTERY, START


def estimate(history: MarketHistory, shrink: bool):
    mm = MarketMaker(
        [Underlying(name="FED", underlying_id=FED, value=START[FED]),
         Underlying(name="AJR", underlying_id=AJR, value=START[AJR]),
         Underlying(name="THR", underlying_id=THR, value=START[THR])],
        list(BATTERY), 100.0,
    )
    model = mm._estimate_model(history)
    if shrink:
        return model
    # Rebuild the raw-OLS (unshrunk) variant from the same data.
    values = history.values_by_underlying_id
    rates, ajr, thr = list(values[FED]), list(values[AJR]), list(values[THR])
    n = min(len(rates), len(ajr), len(thr))
    step = 0.25
    rate_changes = [round(rates[i + 1] - rates[i], 2) for i in range(n - 1)]
    xs, up_ys, down_ys = [], [], []
    for i in range(n - 1):
        if rates[i] <= step / 2.0:
            continue
        xs.append(rates[i])
        up_ys.append(1.0 if rate_changes[i] > step / 2.0 else 0.0)
        down_ys.append(1.0 if rate_changes[i] < -step / 2.0 else 0.0)
    up_int, up_slope = _fit_line(xs, up_ys)
    down_int, down_slope = _fit_line(xs, down_ys)
    reversion = max((down_slope - up_slope) / 2.0, 0.0)  # NO shrink, NO clamp
    mean_rate = sum(xs) / len(xs) if xs else 2.0
    up_int = (up_int + up_slope * mean_rate) + reversion * mean_rate
    down_int = (down_int + down_slope * mean_rate) - reversion * mean_rate
    log_a, log_t, deltas = [], [], []
    for i in range(n - 1):
        if ajr[i] <= 0 or ajr[i + 1] <= 0 or thr[i] <= 0 or thr[i + 1] <= 0:
            continue
        log_a.append(math.log(ajr[i + 1] / ajr[i]))
        log_t.append(math.log(thr[i + 1] / thr[i]))
        deltas.append(rate_changes[i])
    drift_a, beta_a = _fit_line(deltas, log_a)
    drift_t, beta_t = _fit_line(deltas, log_t)
    m = len(deltas)
    resid_a = [y - drift_a - beta_a * x for x, y in zip(deltas, log_a)]
    resid_t = [y - drift_t - beta_t * x for x, y in zip(deltas, log_t)]
    var_a = max(sum(e * e for e in resid_a) / m, 1e-12)
    var_t = max(sum(e * e for e in resid_t) / m, 1e-12)
    cov = sum(a * b for a, b in zip(resid_a, resid_t)) / m
    cap = math.sqrt(var_a * var_t)
    cov = min(max(cov, -cap), cap)
    from Market_Maker import _CompanyLaw
    return _MarketModel(
        rate_step=step, up_intercept=up_int, up_slope=-reversion,
        down_intercept=down_int, down_slope=reversion,
        company_laws={
            AJR: _CompanyLaw(drift=drift_a, rate_beta=beta_a, var=var_a),
            THR: _CompanyLaw(drift=drift_t, rate_beta=beta_t, var=var_t),
        },
        resid_cov=cov, n_obs=m,
    )


def main() -> None:
    MarketMaker.TELEMETRY = False
    errs_raw, errs_shrunk = [], []
    for seed in range(200):
        rng = random.Random(9000 + seed)
        params = _params(rng)
        true_model = _MarketModel.from_parameters(params)
        random.seed(rng.randrange(1 << 30))
        values = dict(START)
        hist = {k: [v] for k, v in values.items()}
        for _ in range(18):
            values = params.advance_step(values)
            for k in hist:
                hist[k].append(values[k])
        history = MarketHistory(values_by_underlying_id={k: tuple(v) for k, v in hist.items()})
        vals_now = {FED: hist[FED][-1], AJR: hist[AJR][-1], THR: hist[THR][-1]}
        m_raw = estimate(history, shrink=False)
        m_shr = estimate(history, shrink=True)
        for option in BATTERY:
            t = _price_with_model(true_model, option, vals_now)
            errs_raw.append((_price_with_model(m_raw, option, vals_now) - t) ** 2)
            errs_shrunk.append((_price_with_model(m_shr, option, vals_now) - t) ** 2)
    rmse_raw = math.sqrt(statistics.fmean(errs_raw))
    rmse_shr = math.sqrt(statistics.fmean(errs_shrunk))
    print(f"18-day warm-up theo RMSE over {len(errs_raw)} option-scenarios:")
    print(f"  raw OLS   : {rmse_raw:.4f}")
    print(f"  shrunk    : {rmse_shr:.4f}")
    print(f"  reduction : {100 * (1 - rmse_shr / rmse_raw):.1f}%")


if __name__ == "__main__":
    main()
