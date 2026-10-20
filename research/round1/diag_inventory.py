"""Verify the inventory sign fix: skew must follow TRUE net position, not gross volume."""
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
opt = BinaryOption(legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0),), option_id=1,
                   steps_until_expiry=2, strike=1000.0)

mm = MarketMaker(unds, [opt], 1000.0)
print(f"{'trade':>22}{'true net':>10}{'tracked':>9}{'skew':>8}   status")
true_net = 0
fails = 0
for label, q in [("buy 5", +5), ("sell 5", -5), ("buy 5", +5), ("sell 5", -5),
                 ("sell 20", -20), ("buy 20", +20), ("buy 40", +40)]:
    mm.on_trade(opt, 0.50, q, 999)
    true_net += q
    tracked = mm._net_lots[AJARAI_UNDERLYING_ID]
    skew = min(max(MarketMaker.SKEW_PER_LOT * mm._net_dir_lots(opt),
                   -MarketMaker.SKEW_CAP), MarketMaker.SKEW_CAP)
    ok = tracked == true_net
    fails += not ok
    print(f"{label:>22}{true_net:>10}{tracked:>9}{skew:>8.3f}   {'OK' if ok else 'WRONG'}")

# a long position must lower our marks, a short position must raise them
mm2 = MarketMaker(unds, [opt], 1000.0)
mm2.on_trade(opt, 0.50, +40, 1)
long_skew = MarketMaker.SKEW_PER_LOT * mm2._net_dir_lots(opt)
mm3 = MarketMaker(unds, [opt], 1000.0)
mm3.on_trade(opt, 0.50, -40, 1)
short_skew = MarketMaker.SKEW_PER_LOT * mm3._net_dir_lots(opt)
print(f"\nlong 40  -> skew {long_skew:+.3f} (must be > 0: mark down, lean to sell)")
print(f"short 40 -> skew {short_skew:+.3f} (must be < 0: mark up, lean to buy)")
fails += not (long_skew > 0 > short_skew)

print(f"\n{'INVENTORY SIGN CORRECT' if fails == 0 else f'{fails} FAILURES'}")
sys.exit(0 if fails == 0 else 1)
