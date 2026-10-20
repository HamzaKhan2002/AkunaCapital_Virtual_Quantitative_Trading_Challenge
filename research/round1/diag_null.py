"""Why did free-roll change nothing, and what is the copysign bug actually worth?

Part A: fills = min(displayed size, allocated share). Run 11's logged fills show
the share, so we can check whether 40 was ever the binding constraint.
Part B: net_lots uses copysign(quantity, weight), which drops the sign of
quantity. Track what the skew does to our book over a session.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Market_Maker_2 import MarketMaker  # noqa: E402

print("=== A. was displayed size ever binding in Run 11? ===")
# (label, order qty, our displayed size, our actual fill) straight from the log
LOG = [
    ("TC2 sell-6 @ bid 0.00 (tie w/ Stalemate)", 6, 40, 3),
    ("TC2 buy-2  @ offer 0.15", 2, 2, 2),
    ("TC3 buy-3  @ offer 0.27", 3, 6, 3),
    ("TC3 buy-4  @ offer 1.00 (tie w/ Stalemate)", 4, 40, 2),
]
print(f"{'case':>44}{'order':>7}{'shown':>7}{'filled':>8}{'share':>8}  binding?")
for label, order, shown, filled in LOG:
    binding = filled >= shown
    print(f"{label:>44}{order:>7}{shown:>7}{filled:>8}{filled:>8}  "
          f"{'YES' if binding else 'no - size was already above our share'}")
print("\n  -> at tie prices we get order/2 (equal split, size-invariant).")
print("  -> raising 40 to 500 can only matter if our share ever exceeded 40,")
print("     i.e. a single order above 80 lots at a 0.00/1.00 tie. None occurred.")

print("\n=== B. copysign bug: what the inventory skew actually does ===")
print("net_lots += copysign(quantity, leg.weight)  ->  |quantity| * sign(weight)")
print("so BUYS and SELLS both push the same direction; it tracks GROSS, not net.\n")
gross = 0
print(f"{'after trade':>12}{'true net':>10}{'buggy net':>11}{'skew':>8}"
      f"{'offer edge':>12}{'bid edge':>10}")
true_net = 0
BASE, W = 0.035, 0.035
for i, q in enumerate([+5, -5, +5, -5, +5, -5, +5, -5], 1):
    true_net += q
    gross += int(math.copysign(q, 1.0))          # the bug
    skew = min(max(MarketMaker.SKEW_PER_LOT * gross, -MarketMaker.SKEW_CAP),
               MarketMaker.SKEW_CAP)
    # v = theo - skew, so offer = theo - skew + W and bid = theo - skew - W
    print(f"{i:>12}{true_net:>10}{gross:>11}{skew:>8.3f}{W - skew:>12.3f}{W + skew:>10.3f}")
print(f"\n  true net position oscillates around 0, but the buggy counter only grows.")
print(f"  once gross >= {int(MarketMaker.SKEW_CAP / MarketMaker.SKEW_PER_LOT)} lots the skew pins at "
      f"{MarketMaker.SKEW_CAP:.2f} for the REST of the session:")
print(f"    offer edge collapses {BASE:.3f} -> {BASE - MarketMaker.SKEW_CAP:+.3f}  (we sell at ~fair value)")
print(f"    bid edge inflates    {BASE:.3f} -> {BASE + MarketMaker.SKEW_CAP:+.3f}  (we stop winning buys)")
