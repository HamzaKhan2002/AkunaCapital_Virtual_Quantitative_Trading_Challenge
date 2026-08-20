"""Fit the shrinkage priors so sigma_eps is honest: target P(|err| > 1 sigma) ~ 0.32."""
import os
import sys
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calibrate_sigma as cal  # noqa: E402
from Market_Maker_2 import (  # noqa: E402
    BinaryOption, MarketHistory, MarketMaker, OptionLeg, Underlying, _price, _sigma_eps,
)
import math  # noqa: E402
import random  # noqa: E402


def coverage(n_warm: int, trials: int = 300):
    rows: dict[str, list[tuple[float, float]]] = {"deep": [], "mid": [], "ATM": []}
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
            rows["deep" if pt < 0.15 or pt > 0.85 else "ATM" if 0.35 <= pt <= 0.65
                 else "mid"].append((abs(_price(mm._model, opt, v) - pt), _sigma_eps(mm._model, opt, v)))
    return rows


BASE = (MarketMaker.DRIFT_PRIOR, MarketMaker.BETA_PRIOR)
print("target: P(|err| > 1 sigma) ~ 0.32 (honest 1-sigma). Lower sigma = tighter quotes.\n")
print(f"{'d_prior':>9}{'b_prior':>9}   " + "".join(f"{b:>26}" for b in ("deep", "mid", "ATM")))
print(f"{'':>18}   " + "".join(f"{'cov':>9}{'sig':>9}{'err':>8}" for _ in range(3)))
for dp, bp in [(0.002, 0.03), (0.002, 0.06), (0.003, 0.09), (0.003, 0.12), (0.004, 0.16)]:
    MarketMaker.DRIFT_PRIOR, MarketMaker.BETA_PRIOR = dp, bp
    rows = coverage(18)
    line = f"{dp:>9.3f}{bp:>9.2f}   "
    for b in ("deep", "mid", "ATM"):
        r = rows[b]
        cov = sum(1 for e, s in r if e > s) / len(r)
        line += f"{cov:>9.3f}{mean(s for _, s in r):>9.4f}{mean(e for e, _ in r):>8.4f}"
    print(line)
MarketMaker.DRIFT_PRIOR, MarketMaker.BETA_PRIOR = BASE
