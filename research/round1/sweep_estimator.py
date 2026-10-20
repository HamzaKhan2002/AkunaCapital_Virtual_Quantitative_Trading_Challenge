"""Sweep estimator shrinkage against ACTUAL theo error. Matched draws across settings."""
import os
import sys
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calibrate_sigma as cal  # noqa: E402
from Market_Maker_2 import (  # noqa: E402
    BinaryOption, MarketHistory, MarketMaker, OptionLeg, Underlying, _price,
)
import math  # noqa: E402
import random  # noqa: E402


def measure(n_warm: int, trials: int = 400) -> dict[str, float]:
    """Mean |theo error| by bucket, using whatever MarketMaker's class knobs are set to."""
    buckets: dict[str, list[float]] = {"deep": [], "mid": [], "ATM": []}
    for trial in range(trials):
        rng = random.Random(50000 + trial)
        mp = cal.draw_params(rng)
        v = {1: max(round(rng.uniform(0.5, 5.0) * 4) / 4, 0.0),
             2: round(rng.uniform(400, 1500), 2), 3: round(rng.uniform(400, 1500), 2)}
        hist = {k: [x] for k, x in v.items()}
        for _ in range(n_warm - 1):
            v = cal.step(mp, v, rng)
            for k in hist:
                hist[k].append(v[k])
        unds = [Underlying("FED", 1, v[1]), Underlying("AJR", 2, v[2]), Underlying("THR", 3, v[3])]
        mm = MarketMaker(unds, [], 100.0)
        mm.warm_up(MarketHistory(values_by_underlying_id={k: tuple(x) for k, x in hist.items()}))
        if mm._model is None:
            continue
        tm = cal.true_model(mp)
        for oi in range(8):
            steps = rng.choice([1, 2, 3, 5])
            kind = rng.random()
            if kind < 0.35:
                opt = BinaryOption(legs=(OptionLeg(1, 1.0),), option_id=oi, steps_until_expiry=steps,
                                   strike=max(round((v[1] + 0.25 * rng.randint(-3, 3)) * 4) / 4, 0.0))
            elif kind < 0.85:
                u = rng.choice([2, 3])
                opt = BinaryOption(legs=(OptionLeg(u, 1.0),), option_id=oi, steps_until_expiry=steps,
                                   strike=round(v[u] * math.exp(rng.gauss(0, 0.06)), 2))
            else:
                w = rng.choice([1.0, -1.0])
                opt = BinaryOption(legs=(OptionLeg(2, w), OptionLeg(3, -w)), option_id=oi,
                                   steps_until_expiry=steps, strike=0.0)
            pt = _price(tm, opt, v)
            err = abs(_price(mm._model, opt, v) - pt)
            buckets["deep" if pt < 0.15 or pt > 0.85 else "ATM" if 0.35 <= pt <= 0.65 else "mid"].append(err)
    return {k: mean(vs) for k, vs in buckets.items() if vs}


BASE = (MarketMaker.DRIFT_SHRINK, MarketMaker.DRIFT_CLAMP)
print("DRIFT shrinkage sweep -- mean |theo error| (matched draws)\n")
for n_warm in (18, 30):
    print(f"--- warm-up {n_warm} days ---")
    print(f"{'shrinkN':>9}{'clamp':>8}{'deep':>9}{'mid':>9}{'ATM':>9}{'overall':>10}")
    for shrink, clamp in [(40.0, 0.01), (100.0, 0.01), (200.0, 0.01),
                          (40.0, 0.002), (100.0, 0.002), (1e9, 0.01)]:
        MarketMaker.DRIFT_SHRINK, MarketMaker.DRIFT_CLAMP = shrink, clamp
        r = measure(n_warm)
        overall = mean(list(r.values()))
        tag = "  <- drift=0" if shrink > 1e8 else ""
        print(f"{shrink:>9.0f}{clamp:>8.3f}{r['deep']:>9.4f}{r['mid']:>9.4f}"
              f"{r['ATM']:>9.4f}{overall:>10.4f}{tag}")
    print()
MarketMaker.DRIFT_SHRINK, MarketMaker.DRIFT_CLAMP = BASE
