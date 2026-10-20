"""AUDIT: what did the post-Run-11 changes actually do to the reported SEs?

Run 11 shipped:  se_drift = sd/sqrt(m),          se_beta = sd/sqrt(vx*m)
Current ships:   se_drift = k_d*sd/sqrt(m) + (1-k_d)*DRIFT_PRIOR
                 se_beta  = k_b*sd/sqrt(vx*m) + (1-k_b)*BETA_PRIOR
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Market_Maker_2 import MarketMaker  # noqa: E402

m = 17          # 18-day warm-up
sd = 0.025      # typical daily residual log-vol (TC1: idio .010-.012, sector 1.0*.02)
vx = 0.03       # variance of daily rate change on the 0.25 grid

old_sd_e = sd / math.sqrt(m)
old_sb_e = sd / math.sqrt(vx * m)
k_d = m / (m + MarketMaker.DRIFT_SHRINK)
k_b = m / (m + MarketMaker.BETA_SHRINK)
new_sd_e = k_d * old_sd_e + (1 - k_d) * MarketMaker.DRIFT_PRIOR
new_sb_e = k_b * old_sb_e + (1 - k_b) * MarketMaker.BETA_PRIOR

print(f"{'':>12}{'Run 11':>10}{'current':>10}{'ratio':>9}")
print(f"{'se_drift':>12}{old_sd_e:>10.4f}{new_sd_e:>10.4f}{new_sd_e / old_sd_e:>9.2f}x")
print(f"{'se_beta':>12}{old_sb_e:>10.4f}{new_sb_e:>10.4f}{new_sb_e / old_sb_e:>9.2f}x")

print(f"\nTRUE parameter magnitudes actually used by the grader (Test Case 1):")
print(f"  drifts      = 0.0010, 0.0015   -> our DRIFT_PRIOR = {MarketMaker.DRIFT_PRIOR}")
print(f"  rate_betas  = -0.020, -0.015   -> our BETA_PRIOR  = {MarketMaker.BETA_PRIOR}")
print(f"  BETA_PRIOR is {MarketMaker.BETA_PRIOR / 0.02:.0f}x the true beta magnitude.")

print("\nimpact on a company option: beta uncertainty enters the log-return as beta*dr")
for T, dr in ((1, 0.25), (3, 0.5), (5, 0.75)):
    tot = sd * math.sqrt(T)
    print(f"  T={T}d, |dr|={dr}: run11 beta noise={old_sb_e * dr:.4f} vs current={new_sb_e * dr:.4f}"
          f"   (total return sd={tot:.4f})  -> current beta noise is "
          f"{new_sb_e * dr / tot:.2f}x the ENTIRE return sd")
