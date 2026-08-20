"""In-domain sigma honesty of the CURRENT shipped code, by option type."""
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

rows = {"FED": [], "company": [], "spread": []}
for trial in range(250):
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

print("honest 1-sigma => cov ~0.317. cov >> 0.317 = we quote INSIDE our real error.")
print(f"{'kind':>9}{'n':>6}{'mean|err|':>11}{'mean sig':>10}{'cov(1s)':>9}{'halfwidth':>11}"
      f"{'width/err':>11}")
for kind, r in rows.items():
    cov = sum(1 for e, s, _ in r if e > s) / len(r)
    me, ms, mw = (mean(x[i] for x in r) for i in range(3))
    print(f"{kind:>9}{len(r):>6}{me:>11.4f}{ms:>10.4f}{cov:>9.3f}{mw:>11.4f}{mw / me:>11.2f}")
