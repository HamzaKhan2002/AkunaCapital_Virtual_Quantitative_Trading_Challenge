"""Verify the free-roll path: zero-lock prices get size, and cannot lose money."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Market_Maker_2 import (  # noqa: E402
    AJARAI_UNDERLYING_ID, FED_FUNDS_RATE_UNDERLYING_ID, THERIODIC_UNDERLYING_ID,
    BinaryOption, MarketMaker, OptionLeg, Underlying,
)

unds = [Underlying("FED", FED_FUNDS_RATE_UNDERLYING_ID, 2.0),
        Underlying("AJR", AJARAI_UNDERLYING_ID, 1000.0),
        Underlying("THR", THERIODIC_UNDERLYING_ID, 750.0)]

print("book across moneyness ($10 book, no warm-up):")
print(f"{'strike':>8}{'theo':>7}{'bid':>7}{'off':>7}{'bidQ':>7}{'offQ':>7}")
for strike in (500.0, 850.0, 950.0, 1000.0, 1050.0, 1200.0, 1800.0):
    mm = MarketMaker(unds, [], 10.0)
    opt = BinaryOption(legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0),), option_id=1,
                       steps_until_expiry=2, strike=strike)
    q = mm.quote(opt, 555)
    print(f"{strike:>8.0f}{mm.price_option(opt):>7.2f}{q.bid_price:>7.2f}{q.offer_price:>7.2f}"
          f"{q.bid_quantity:>7}{q.offer_quantity:>7}")

print("\nfree-roll safety: fill the whole free-roll size, worst-case settlement")
for side, price, payoff_worst in (("buy @0.00", 0.00, 0.0), ("sell @1.00", 1.00, 1.0)):
    mm = MarketMaker(unds, [], 10.0)
    opt = BinaryOption(legs=(OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, 1.0),), option_id=9,
                       steps_until_expiry=1, strike=99.0 if payoff_worst == 0.0 else 0.0)
    qty = MarketMaker.FREE_ROLL_SIZE if price == 0.0 else -MarketMaker.FREE_ROLL_SIZE
    before = mm._free
    mm.on_trade(opt, price, qty, 777)
    locked = before - mm._free
    mm._settle(BinaryOption(legs=opt.legs, option_id=opt.option_id, steps_until_expiry=0,
                            strike=opt.strike), {1: 2.0, 2: 1000.0, 3: 750.0})
    print(f"  {side:>11} x{abs(qty)}: margin locked = {locked:.2f}, "
          f"free after worst-case expiry = {mm._free:.2f} (started {before:.2f})")
    assert locked <= 1e-9, "free roll must lock zero margin"
    assert mm._free >= before - 1e-9, "free roll must never lose"
print("  OK: zero lock, non-negative outcome in both directions")
