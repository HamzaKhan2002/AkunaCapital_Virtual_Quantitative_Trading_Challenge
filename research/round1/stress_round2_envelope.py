"""
THE CRITICAL TEST: mm6 deploys 70-80% of a $10 book. Every stress run we have
used ~1 RFQ/day, calibrated to OUR grader. The community simulator's envelope is
2-10 RFQ/day, and its $10 scenario is described as one where "solvency, not edge,
is the binding constraint -- and the day-end check is unforgiving".

Same code goes into round 2. A bankruptcy scores 0, below the 0.4 floor, so this
is the one failure that cannot be recovered from. If mm6 ruins at high flow on a
small book, the $10 gate is not a missed opportunity -- it is a live grenade.

Sweeps flow rate x capital x flow toxicity, counting insolvencies.
"""
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arena2  # noqa: E402
from arena2 import (FixedWidthBot, FlowConfig, StalemateBot, draw_params,  # noqa: E402
                    run_session)
from audit_adversary import Adaptive, Sniper  # noqa: E402
import Market_Maker_2 as MM2  # noqa: E402
import Market_Maker_6 as MM6  # noqa: E402

MM6.OrderType = MM2.OrderType
MM6.FokOrder = MM2.FokOrder
MM6.BinaryOption = MM2.BinaryOption
MM6.Underlying = MM2.Underlying
MM6.MarketHistory = MM2.MarketHistory

N = 60
W = {"fw05": .05, "fw10": .10, "fw25": .25}


def field(names, mp, cap):
    out = []
    for n in names:
        if n == "stale":
            out.append(StalemateBot())
        elif n == "sniper":
            out.append(Sniper(mp, cap))
        elif n == "adapt":
            out.append(Adaptive(mp, cap))
        else:
            out.append(FixedWidthBot(f"FW{n[2:]}", mp, W[n], 60))
    return out


def sweep(module, label):
    print(f"\n{label}")
    print(f"  {'RFQ/day':>8}{'FOK/day':>8}" + "".join(f"{'$' + str(c):>12}"
                                                      for c in (10, 20, 40, 60)))
    worst = 0
    for rfq, fok in ((1, 1), (3, 2), (5, 3), (8, 4), (10, 4)):
        flow = FlowConfig("sharp", rfq, fok, 12, big_order_prob=0.15, big_qty_hi=200)
        row = []
        for cap in (10.0, 20.0, 40.0, 60.0):
            ruin = tot = 0
            for names in (["stale"], ["fw25", "stale"], ["sniper", "stale"],
                          ["adapt", "fw05"]):
                for s in range(N):
                    arena2.MarketMaker = module.MarketMaker
                    rng = random.Random(950_000 + s)
                    mp = draw_params(rng)
                    sc, _ = run_session(mp, flow, field(names, mp, cap), cap,
                                        950_000 + s)
                    tot += 1
                    ruin += sc == 0.0
            worst = max(worst, ruin)
            row.append(f"{ruin}/{tot}")
        print(f"  {rfq:>8}{fok:>8}" + "".join(f"{c:>12}" for c in row))
    return worst


def main() -> int:
    print("=" * 74)
    print("RUIN UNDER THE COMMUNITY-SIMULATOR FLOW ENVELOPE (sharp flow, big orders)")
    print("=" * 74)
    w6 = sweep(MM6, "mm6 (SHIPPING: 70/80% budget + ladder on <= $10.5)")
    w2 = sweep(MM2, "mm2 (baseline 25/40% budget, no ladder) -- control")

    print("\n" + "=" * 74)
    print(f"  worst single cell: mm6 {w6} ruins, mm2 {w2} ruins")
    if w6 == 0:
        print("  PASS: mm6 never ruins anywhere in the envelope. The $10 gate is")
        print("  safe to carry into round 2 unchanged.")
    else:
        print("  *** FAIL: mm6 ruins under flow rates we never tested. The $10")
        print("  aggression is a liability, not just a missed opportunity.")
    return w6


if __name__ == "__main__":
    sys.exit(main())
