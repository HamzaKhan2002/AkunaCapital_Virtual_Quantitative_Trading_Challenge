"""Sweep CAPITAL_WIDEN to locate the arena optimum, all vs the SAME baseline arm."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arena_ab import ab  # noqa: E402
from Market_Maker_2 import MarketMaker  # noqa: E402

BASE = 0.25


def mk(v):
    def setter():
        MarketMaker.CAPITAL_WIDEN = v
    return setter


print("all comparisons vs the SAME baseline arm (CAPITAL_WIDEN=0.25), 640 paired sessions each")
results = {}
for cand in (0.40, 0.60, 0.80, 1.20):
    mean, lo, hi = ab(f"base={BASE}", mk(BASE), f"cand={cand}", mk(cand), n=80)
    results[cand] = (mean, lo, hi)

print("\n" + "=" * 62)
print(f"{'CAPITAL_WIDEN':>15}{'delta vs 0.25':>16}{'95% CI':>26}")
for k, (m, lo, hi) in results.items():
    flag = "  <- significant" if lo > 0 or hi < 0 else ""
    print(f"{k:>15.2f}{m:>+16.4f}   [{lo:+.4f}, {hi:+.4f}]{flag}")
best = max(results, key=lambda k: results[k][0])
print(f"\narena-optimal among tested: CAPITAL_WIDEN = {best} (delta {results[best][0]:+.4f})")
