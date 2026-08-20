"""Second sweep: does drift=0 still win at 60 days, and are beta/rho shrinkage tuned?"""
import os
import sys
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sweep_estimator import measure  # noqa: E402
from Market_Maker_2 import MarketMaker  # noqa: E402

BASE = (MarketMaker.DRIFT_SHRINK, MarketMaker.DRIFT_CLAMP,
        MarketMaker.BETA_SHRINK, MarketMaker.RHO_SHRINK)

print("--- drift at 60-day warm-up (does shrink-to-zero still win?) ---")
print(f"{'shrinkN':>9}{'deep':>9}{'mid':>9}{'ATM':>9}{'overall':>10}")
for shrink in (40.0, 200.0, 1e9):
    MarketMaker.DRIFT_SHRINK = shrink
    r = measure(60)
    print(f"{shrink:>9.0f}{r['deep']:>9.4f}{r['mid']:>9.4f}{r['ATM']:>9.4f}"
          f"{mean(list(r.values())):>10.4f}")

MarketMaker.DRIFT_SHRINK = 200.0
print("\n--- beta shrinkage (at DRIFT_SHRINK=200, 18-day) ---")
print(f"{'betaN':>9}{'deep':>9}{'mid':>9}{'ATM':>9}{'overall':>10}")
for bs in (2.0, 8.0, 30.0, 1e9):
    MarketMaker.BETA_SHRINK = bs
    r = measure(18)
    print(f"{bs:>9.0f}{r['deep']:>9.4f}{r['mid']:>9.4f}{r['ATM']:>9.4f}"
          f"{mean(list(r.values())):>10.4f}")
MarketMaker.BETA_SHRINK = BASE[2]

print("\n--- rho shrinkage (at DRIFT_SHRINK=200, 18-day) ---")
print(f"{'rhoN':>9}{'deep':>9}{'mid':>9}{'ATM':>9}{'overall':>10}")
for rs in (0.0, 10.0, 40.0, 1e9):
    MarketMaker.RHO_SHRINK = rs
    r = measure(18)
    print(f"{rs:>9.0f}{r['deep']:>9.4f}{r['mid']:>9.4f}{r['ATM']:>9.4f}"
          f"{mean(list(r.values())):>10.4f}")

(MarketMaker.DRIFT_SHRINK, MarketMaker.DRIFT_CLAMP,
 MarketMaker.BETA_SHRINK, MarketMaker.RHO_SHRINK) = BASE
