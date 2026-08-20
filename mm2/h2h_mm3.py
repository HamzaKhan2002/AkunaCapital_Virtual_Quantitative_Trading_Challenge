"""
mm2 vs mm3, seed-paired, calibrated flow (1 RFQ + 1 FOK/day), known rosters.

The arena is NOT trusted for absolute rank (E53/E55). It is used here for
directional, seed-paired mechanism claims only. Pre-registered predictions:

  P1  capture: mm3 out-earns mm2 in the flow-rich fixed-width tests
      (TC8/TC10-like), because QUOTE_LOCK_FRAC 0.25->0.45 raises displayed size
      and every extra lot is taken FROM the width bot (deny-edge is 1:1).
  P2  starvation: the opponents' mean PnL falls under mm3 in those same tests.
  P3  safety: zero bankruptcies for mm3 across all sessions, incl. sharp flow.
  P4  free-roll tests (TC5) unchanged: budget does not touch 0.00/1.00 quoting.

Failure of P1/P2 kills the change. Failure of P3 kills it absolutely.
"""
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arena2  # noqa: E402
from arena2 import KNOWN_TESTS, FlowConfig, build, draw_params, run_session  # noqa: E402
import Market_Maker_2 as MM2  # noqa: E402
import Market_Maker_3 as MM3  # noqa: E402

CAL = FlowConfig("neutral", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)
SHARP = FlowConfig("sharp", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)
N = 80


def arm(module, tc, cap, names, flow, seed):
    arena2.MarketMaker = module.MarketMaker
    rng = random.Random(seed)
    mp = draw_params(rng)
    score, pnl = run_session(mp, flow, build(names, mp), cap, seed)
    ours = pnl.pop("Hamza Khan", 0.0)
    return score, ours, pnl


def main() -> int:
    fail = 0
    print(f"{'test':<6}{'cap':>5}  {'roster':<18}"
          f"{'mm2 PnL':>9}{'mm3 PnL':>9}{'d_us':>8} | {'opp mm2':>9}{'opp mm3':>9}"
          f"{'d_opp':>8} | {'mm3 wins':>9}")
    for tc, (cap, names, _a) in KNOWN_TESTS.items():
        us2, us3, op2, op3, wins = [], [], [], [], 0
        for s in range(N):
            _, o2, p2 = arm(MM2, tc, cap, names, CAL, 70_000 + s)
            _, o3, p3 = arm(MM3, tc, cap, names, CAL, 70_000 + s)
            us2.append(o2)
            us3.append(o3)
            op2.append(statistics.fmean(p2.values()))
            op3.append(statistics.fmean(p3.values()))
            wins += o3 > o2
        d_us = statistics.fmean(us3) - statistics.fmean(us2)
        d_op = statistics.fmean(op3) - statistics.fmean(op2)
        print(f"{tc:<6}{cap:>5.0f}  {'+'.join(names):<18}"
              f"{statistics.fmean(us2):>+9.2f}{statistics.fmean(us3):>+9.2f}{d_us:>+8.2f} |"
              f"{statistics.fmean(op2):>+9.2f}{statistics.fmean(op3):>+9.2f}{d_op:>+8.2f} |"
              f"{wins:>6}/{N}")

    # P3: ruin under sharp flow at the raised budgets, all rosters
    bank = tot = 0
    for tc, (cap, names, _a) in KNOWN_TESTS.items():
        for s in range(N):
            arena2.MarketMaker = MM3.MarketMaker
            rng = random.Random(90_000 + s)
            mp = draw_params(rng)
            score, pnl = run_session(mp, SHARP, build(names, mp), cap, 90_000 + s)
            tot += 1
            if score == 0.0:
                bank += 1
    print(f"\nP3 sharp-flow ruin check: {bank} bankruptcies / {tot} sessions")
    if bank:
        fail += 1
        print("*** P3 FAIL: raised budgets can bankrupt. DO NOT SUBMIT.")
    else:
        print("P3 PASS.")
    return fail


if __name__ == "__main__":
    sys.exit(main())
