"""Sweep the sigma priors for per-type coverage ~0.317 (honest 1-sigma)."""
import math
import os
import random
import sys
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calibrate_sigma as cal  # noqa: E402
from map_policy import draw_real  # noqa: E402
from Market_Maker_2 import (  # noqa: E402
    BinaryOption, MarketHistory, MarketMaker, OptionLeg, Underlying, _price, _sigma_eps,
)


def measure(trials: int = 250):
    rows = {"FED": [], "company": [], "spread": []}
    for trial in range(trials):
        rng = random.Random(90000 + trial)
        mp = draw_real(rng)
        v = {1: max(round(rng.uniform(0.5, 5.0) * 4) / 4, 0.0),
             2: round(rng.uniform(400, 1500), 2), 3: round(rng.uniform(400, 1500), 2)}
        hist = {k: [x] for k, x in v.items()}
        for _ in range(17):
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
            pt = _price(tm, opt, v)
            q = mm.quote(opt, 4242)
            rows[kind].append((abs(_price(mm._model, opt, v) - pt), _sigma_eps(mm._model, opt, v),
                               (q.offer_price - q.bid_price) / 2.0))
    return rows


BASE = (MarketMaker.BETA_PRIOR, MarketMaker.STRENGTH_PRIOR)
print("target cov 0.317. cov>0.317 = sigma too SMALL (we quote inside our error).")
print(f"{'beta':>6}{'stren':>7}   " + "".join(f"{k:>24}" for k in ("FED", "company", "spread")))
print(f"{'':>13}   " + "".join(f"{'cov':>8}{'width':>8}{'w/err':>8}" for _ in range(3)))
for bp, sp in [(0.02, 0.10), (0.03, 0.14), (0.04, 0.18), (0.05, 0.22)]:
    MarketMaker.BETA_PRIOR, MarketMaker.STRENGTH_PRIOR = bp, sp
    rows = measure()
    line = f"{bp:>6.3f}{sp:>7.2f}   "
    for kind in ("FED", "company", "spread"):
        r = rows[kind]
        cov = sum(1 for e, s, _ in r if e > s) / len(r)
        me = mean(e for e, _, _ in r)
        mw = mean(w for *_, w in r)
        line += f"{cov:>8.3f}{mw:>8.4f}{mw / me:>8.2f}"
    print(line)
MarketMaker.BETA_PRIOR, MarketMaker.STRENGTH_PRIOR = BASE
