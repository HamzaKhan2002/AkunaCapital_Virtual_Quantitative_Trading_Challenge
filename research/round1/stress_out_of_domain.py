"""Out-of-domain ruin stress: the committee's one immediately actionable item (E54 T7).

The only ruin-capable Round-2 risk identified: parameter regimes OUTSIDE the
TC1-anchored domain our estimator was tuned on. sigma_eps measures sampling
variance around the SHRUNK estimate -- it cannot see shrinkage BIAS, so in a
trending / high-vol / strong-beta world our theos can be systematically wrong.
The question here is narrow and binary: does systematic mispricing ever
BANKRUPT us (score 0 < 0.4-for-surviving)? Solvency comes from the ledger and
sizing discipline, which are price-independent -- verify that holds.

Regimes deliberately far outside the shrinkage priors and Phase-1 draws.
"""
import math
import os
import random
import sys
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arena2 import FixedWidthBot, FlowConfig, StalemateBot, run_session  # noqa: E402
from Market_Maker_2 import MarketParameters  # noqa: E402

REGIMES = {
    "strong trend up":    dict(drift=+0.012, idio=0.020, beta=-0.02, sector=0.02),
    "strong trend down":  dict(drift=-0.012, idio=0.020, beta=-0.02, sector=0.02),
    "extreme vol":        dict(drift=0.000, idio=0.080, beta=-0.02, sector=0.05),
    "huge rate beta":     dict(drift=0.000, idio=0.015, beta=-0.30, sector=0.02),
    "dead calm":          dict(drift=0.000, idio=0.002, beta=0.00, sector=0.002),
    "trend + vol + beta": dict(drift=+0.010, idio=0.060, beta=-0.25, sector=0.04),
}


def params_for(reg: dict, rng: random.Random) -> MarketParameters:
    return MarketParameters(
        ajarai_drift=reg["drift"], ajarai_idio_std_dev=reg["idio"],
        ajarai_rate_beta=reg["beta"], ajarai_sector_beta=rng.uniform(0.8, 1.2),
        rate_down_probability=rng.uniform(0.15, 0.45), rate_reversion_strength=rng.uniform(0.0, 0.4),
        rate_up_probability=rng.uniform(0.15, 0.45), sector_std_dev=reg["sector"],
        theriodic_drift=reg["drift"] * rng.uniform(0.5, 1.5), theriodic_idio_std_dev=reg["idio"],
        theriodic_rate_beta=reg["beta"] * rng.uniform(0.5, 1.5),
        theriodic_sector_beta=rng.uniform(0.8, 1.2))


def main() -> None:
    n = 60
    flows = {"dumb": FlowConfig("dumb", 4, 3, 15), "sharp": FlowConfig("sharp", 4, 3, 15)}
    total_sessions = 0
    total_ruin = 0
    print(f"{'regime':>22}{'flow':>8}{'sessions':>10}{'RUINED':>8}{'meanPnL':>10}{'minPnL':>9}{'mean score':>12}")
    for rname, reg in REGIMES.items():
        for fname, fcfg in flows.items():
            ruined = 0
            pnls, scores = [], []
            for s in range(n):
                rng = random.Random(50000 + s)
                mp = params_for(reg, rng)
                opps = [FixedWidthBot("Fixed Width 0.1", mp, 0.10), StalemateBot()]
                for cap in (10.0,):     # smallest book = tightest solvency
                    sc, pnl = run_session(mp, fcfg, opps, cap, seed=50000 + s)
                    scores.append(sc)
                    pnls.append(pnl["Hamza Khan"])
                    if sc == 0.0:
                        ruined += 1
            total_sessions += n
            total_ruin += ruined
            print(f"{rname:>22}{fname:>8}{n:>10}{ruined:>8}{mean(pnls):>+10.2f}"
                  f"{min(pnls):>+9.2f}{mean(scores):>12.3f}")
    print(f"\nTOTAL: {total_ruin} bankruptcies in {total_sessions * 2} sessions "
          f"across {len(REGIMES)} out-of-domain regimes on $10 books")
    print("PASS: solvency discipline is price-independent" if total_ruin == 0
          else "FAIL: RUIN IS REACHABLE OUT OF DOMAIN -- investigate before Round 2")


if __name__ == "__main__":
    main()
