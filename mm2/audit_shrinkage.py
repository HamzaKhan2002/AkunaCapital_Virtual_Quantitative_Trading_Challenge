"""Re-verify the drift/beta shrinkage sweep in the REAL domain (it was fitted on the wide one)."""
import math
import os
import random
import sys
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calibrate_sigma as cal  # noqa: E402
from audit_refit import draw_real  # noqa: E402
from Market_Maker_2 import (  # noqa: E402
    BinaryOption, MarketHistory, MarketMaker, OptionLeg, Underlying, _price,
)


def err_by_kind(n_warm: int, trials: int = 250) -> dict[str, float]:
    acc: dict[str, list[float]] = {"FED": [], "company": [], "spread": []}
    for trial in range(trials):
        rng = random.Random(90000 + trial)
        mp = draw_real(rng)
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
            k = rng.random()
            if k < 0.35:
                kind = "FED"
                opt = BinaryOption(legs=(OptionLeg(1, 1.0),), option_id=oi, steps_until_expiry=steps,
                                   strike=max(round((v[1] + 0.25 * rng.randint(-3, 3)) * 4) / 4, 0.0))
            elif k < 0.85:
                kind = "company"
                u = rng.choice([2, 3])
                opt = BinaryOption(legs=(OptionLeg(u, 1.0),), option_id=oi, steps_until_expiry=steps,
                                   strike=round(v[u] * math.exp(rng.gauss(0, 0.06)), 2))
            else:
                kind = "spread"
                w = rng.choice([1.0, -1.0])
                opt = BinaryOption(legs=(OptionLeg(2, w), OptionLeg(3, -w)), option_id=oi,
                                   steps_until_expiry=steps, strike=0.0)
            acc[kind].append(abs(_price(mm._model, opt, v) - _price(tm, opt, v)))
    return {k: mean(v) for k, v in acc.items() if v}


BASE = (MarketMaker.DRIFT_SHRINK, MarketMaker.BETA_SHRINK)
print("mean |theo error| in the REAL domain -- does shrinkage still win here?\n")
print(f"{'driftN':>8}{'betaN':>8}{'FED':>9}{'company':>10}{'spread':>9}{'overall':>10}")
for ds, bs in [(40.0, 8.0), (200.0, 8.0), (40.0, 100.0), (200.0, 100.0), (200.0, 1e9)]:
    MarketMaker.DRIFT_SHRINK, MarketMaker.BETA_SHRINK = ds, bs
    r = err_by_kind(18)
    tag = "  <- Run 11 (16.9)" if (ds, bs) == (40.0, 8.0) else (
        "  <- current" if (ds, bs) == (200.0, 100.0) else "")
    print(f"{ds:>8.0f}{bs:>8.0f}{r['FED']:>9.4f}{r['company']:>10.4f}{r['spread']:>9.4f}"
          f"{mean(list(r.values())):>10.4f}{tag}")
MarketMaker.DRIFT_SHRINK, MarketMaker.BETA_SHRINK = BASE
