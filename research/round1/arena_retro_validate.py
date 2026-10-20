"""RETROSPECTIVE VALIDATION: does the arena predict changes whose LIVE result we know?

This is the decisive test of whether arena A/B results may be trusted at all.
Known live outcomes, each shipped in isolation and log-verified:
    free-roll  (FREE_ROLL_SIZE 40 -> 500) : +0.5  (16.9 -> 17.4)
    SIZE_CAP   (40 -> 500)                :  0.0  (verified twice)
If the arena reproduces these signs, its A/B verdicts carry weight. If it does
not, its CAPITAL_WIDEN recommendation must be discarded no matter how tight the
confidence interval looks -- a precise answer to the wrong question.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arena_ab import ab  # noqa: E402
from Market_Maker_2 import MarketMaker  # noqa: E402

CASES = [
    # (label_off, label_on, attr, off_value, on_value, live_result)
    ("FREE_ROLL=40", "FREE_ROLL=500", "FREE_ROLL_SIZE", 40, 500, +0.5),
    ("SIZE_CAP=40", "SIZE_CAP=500", "SIZE_CAP", 40, 500, 0.0),
]


def mk(attr, val):
    def setter():
        setattr(MarketMaker, attr, val)
    return setter


print("=" * 70)
print("RETROSPECTIVE ARENA VALIDATION")
print("=" * 70)
results = []
for off_lbl, on_lbl, attr, off_v, on_v, live in CASES:
    mean, lo, hi = ab(off_lbl, mk(attr, off_v), on_lbl, mk(attr, on_v), n=80)
    sig = "gain" if lo > 0 else ("loss" if hi < 0 else "neutral")
    live_sign = "gain" if live > 0.05 else ("loss" if live < -0.05 else "neutral")
    results.append((on_lbl, sig, live_sign, mean, live))

print("\n" + "=" * 70)
print(f"{'change':>18}{'arena says':>13}{'LIVE said':>12}{'arena delta':>14}{'live delta':>12}   match")
ok = 0
for lbl, sig, live_sign, mean, live in results:
    match = "YES" if sig == live_sign else "NO"
    ok += match == "YES"
    print(f"{lbl:>18}{sig:>13}{live_sign:>12}{mean:>+14.4f}{live:>+12.2f}   {match}")
print(f"\narena reproduced {ok}/{len(results)} known live outcomes")
if ok < len(results):
    print("\n=> ARENA FAILS RETROSPECTIVE VALIDATION.")
    print("   Its A/B verdicts (including the CAPITAL_WIDEN recommendation) are NOT")
    print("   evidence about live behaviour and must not drive a submission.")
else:
    print("\n=> arena reproduces known live outcomes; A/B verdicts carry some weight.")
