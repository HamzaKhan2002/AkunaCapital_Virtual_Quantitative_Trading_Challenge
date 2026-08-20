"""AUDIT + REFIT in the DEPLOYMENT domain.

The priors shipped after Run 11 were fitted against calibrate_sigma.draw_params,
which samples rate_beta in [-0.2, 0] -- 10x wider than the only ground truth we
have (Test Case 1: rate_betas -0.020 / -0.015, drifts 0.0010 / 0.0015). Fitting a
prior on a fabricated domain inflated se_beta 4x. Refit here against a draw
grounded in Test Case 1, with a deliberate but bounded spread.
"""
import math
import os
import random
import sys
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calibrate_sigma as cal  # noqa: E402
from Market_Maker_2 import (  # noqa: E402
    BinaryOption, MarketHistory, MarketMaker, MarketParameters, OptionLeg,
    Underlying, _price, _sigma_eps,
)

# Test Case 1 is the one observation of the true generator we have. Spread ~2-3x
# around it so the domain is conservative without being fictional.
TC1 = dict(ajarai_drift=0.001, ajarai_idio_std_dev=0.01, ajarai_rate_beta=-0.02,
           ajarai_sector_beta=1.0, rate_down_probability=0.2, rate_reversion_strength=0.1,
           rate_up_probability=0.25, sector_std_dev=0.02, theriodic_drift=0.0015,
           theriodic_idio_std_dev=0.012, theriodic_rate_beta=-0.015, theriodic_sector_beta=1.0)


def draw_real(rng: random.Random) -> MarketParameters:
    return MarketParameters(
        ajarai_drift=rng.uniform(-0.003, 0.003), ajarai_idio_std_dev=rng.uniform(0.006, 0.025),
        ajarai_rate_beta=-abs(rng.uniform(0.0, 0.05)), ajarai_sector_beta=rng.uniform(0.6, 1.6),
        rate_down_probability=rng.uniform(0.12, 0.35), rate_reversion_strength=rng.uniform(0.0, 0.25),
        rate_up_probability=rng.uniform(0.12, 0.35), sector_std_dev=rng.uniform(0.01, 0.03),
        theriodic_drift=rng.uniform(-0.003, 0.003), theriodic_idio_std_dev=rng.uniform(0.006, 0.025),
        theriodic_rate_beta=-abs(rng.uniform(0.0, 0.05)), theriodic_sector_beta=rng.uniform(0.6, 1.6))


def sample(n_warm: int, trials: int, draw):
    """Returns rows of (kind, |err|, sigma, quote half-width)."""
    rows = []
    for trial in range(trials):
        rng = random.Random(90000 + trial)
        mp = draw(rng)
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
            pt = _price(tm, opt, v)
            q = mm.quote(opt, 4242)
            rows.append((kind, abs(_price(mm._model, opt, v) - pt), _sigma_eps(mm._model, opt, v),
                         (q.offer_price - q.bid_price) / 2.0))
    return rows


def report(tag, rows):
    print(f"  {tag}")
    print(f"    {'kind':>9}{'n':>6}{'mean|err|':>11}{'mean sig':>10}{'cov(1s)':>9}{'halfwidth':>11}")
    for kind in ("FED", "company", "spread"):
        r = [x for x in rows if x[0] == kind]
        if not r:
            continue
        cov = sum(1 for _, e, s, _ in r if e > s) / len(r)
        print(f"    {kind:>9}{len(r):>6}{mean(e for _, e, _, _ in r):>11.4f}"
              f"{mean(s for _, _, s, _ in r):>10.4f}{cov:>9.3f}{mean(w for *_, w in r):>11.4f}")


print("=== 1. CURRENT SHIPPED PRIORS, measured in the REAL domain (18-day) ===")
report(f"DRIFT_PRIOR={MarketMaker.DRIFT_PRIOR}, BETA_PRIOR={MarketMaker.BETA_PRIOR}",
       sample(18, 250, draw_real))

print("\n=== 2. REFIT: sweep priors in the REAL domain (target cov ~0.317) ===")
BASE = (MarketMaker.DRIFT_PRIOR, MarketMaker.BETA_PRIOR)
for dp, bp in [(0.001, 0.01), (0.0015, 0.02), (0.002, 0.03), (0.003, 0.05), (0.004, 0.16)]:
    MarketMaker.DRIFT_PRIOR, MarketMaker.BETA_PRIOR = dp, bp
    report(f"DRIFT_PRIOR={dp}, BETA_PRIOR={bp}", sample(18, 250, draw_real))
MarketMaker.DRIFT_PRIOR, MarketMaker.BETA_PRIOR = BASE
