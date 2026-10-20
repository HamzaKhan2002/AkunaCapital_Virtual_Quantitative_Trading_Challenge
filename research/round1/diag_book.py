"""Before/after of the quote book and size, at the capital scales the grader uses."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Market_Maker_2 import (  # noqa: E402
    AJARAI_UNDERLYING_ID, FED_FUNDS_RATE_UNDERLYING_ID, THERIODIC_UNDERLYING_ID,
    BinaryOption, MarketMaker, OptionLeg, Underlying, _Law, _Model,
)

unds = [Underlying("FED", FED_FUNDS_RATE_UNDERLYING_ID, 2.0),
        Underlying("AJR", AJARAI_UNDERLYING_ID, 1000.0),
        Underlying("THR", THERIODIC_UNDERLYING_ID, 750.0)]

law = _Law(0.0, -0.02, 0.02, se_drift=0.0005, se_beta=0.002, se_sd=0.0005)
tight = _Model(p_up=0.25, p_down=0.25, strength=0.1, target=2.0,
               laws={AJARAI_UNDERLYING_ID: law, THERIODIC_UNDERLYING_ID: law},
               rho=0.5, se_rho=0.02, se_p=0.01, n_obs=400)

print(f"{'theo':>6}{'bid':>7}{'off':>7}{'bidQ':>6}{'offQ':>6}{'bid edge':>10}{'off edge':>10}"
      f"   vs FW0.1 (bid/offer)")
for target in (0.05, 0.2, 0.5, 0.8, 0.9, 0.95):
    mm = MarketMaker(unds, [], 10.0)
    mm._model = tight
    # synthesize an option whose theo lands near `target` by bisecting the strike
    lo, hi = 300.0, 2000.0
    for _ in range(60):
        mid = (lo + hi) / 2
        opt = BinaryOption(legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0),), option_id=1,
                           steps_until_expiry=3, strike=round(mid, 2))
        if mm.price_option(opt) > target:
            lo = mid
        else:
            hi = mid
    opt = BinaryOption(legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0),), option_id=1,
                       steps_until_expiry=3, strike=round((lo + hi) / 2, 2))
    p = mm.price_option(opt)
    q = mm.quote(opt, 12345)
    wb = "US" if q.bid_price > p - 0.05 else "FW"
    wo = "US" if q.offer_price < p + 0.05 else "FW"
    print(f"{p:>6.2f}{q.bid_price:>7.2f}{q.offer_price:>7.2f}{q.bid_quantity:>6}"
          f"{q.offer_quantity:>6}{p - q.bid_price:>10.3f}{q.offer_price - p:>10.3f}"
          f"   {wb:>4} / {wo:>4}")

print("\ncapital-scarcity widening (theo 0.50, $10 book):")
for util in (0.0, 0.3, 0.6, 0.9):
    mm = MarketMaker(unds, [], 10.0)
    mm._model = tight
    mm._locked = util * 10.0
    mm._free = 10.0 - mm._locked
    opt = BinaryOption(legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0),), option_id=1,
                       steps_until_expiry=3, strike=1000.0)
    q = mm.quote(opt, 12345)
    print(f"  util={util:.1f}  {q.bid_price:.2f}/{q.offer_price:.2f} "
          f"width={q.offer_price - q.bid_price:.2f}  sizes {q.bid_quantity}/{q.offer_quantity}")

# The settled rule that sank v6/v7: never quote inside our own estimation error.
# BASE_EDGE is 3.5c, so sigma must be what sets the width at realistic warm-ups.
import math  # noqa: E402
import random  # noqa: E402

from Market_Maker_2 import MarketHistory, _sigma_eps  # noqa: E402

rng = random.Random(11)
mm = MarketMaker(unds, [], 20.0)
mm.warm_up(MarketHistory(values_by_underlying_id={
    1: tuple(max(2.0 + 0.25 * rng.randint(-2, 2), 0.0) for _ in range(18)),
    2: tuple(round(1000 * math.exp(rng.gauss(0, 0.02)), 2) for _ in range(18)),
    3: tuple(round(750 * math.exp(rng.gauss(0, 0.03)), 2) for _ in range(18))}))
print("\n18-day warm-up: does sigma still set the width? (need edge >= sigma)")
print(f"{'theo':>6}{'sigma':>8}{'bid':>7}{'off':>7}{'edge':>7}   binding")
for strike in (900.0, 975.0, 1000.0, 1025.0, 1100.0):
    opt = BinaryOption(legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0),), option_id=7,
                       steps_until_expiry=3, strike=strike)
    p = mm.price_option(opt)
    s = _sigma_eps(mm._the_model(), opt, {u.underlying_id: u.value for u in unds})
    q = mm.quote(opt, 999)
    edge = min(p - q.bid_price, q.offer_price - p)
    print(f"{p:>6.2f}{s:>8.3f}{q.bid_price:>7.2f}{q.offer_price:>7.2f}{edge:>7.3f}"
          f"   {'sigma' if s > 0.035 else 'base'}")

