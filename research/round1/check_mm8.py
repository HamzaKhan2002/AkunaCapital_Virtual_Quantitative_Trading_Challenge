"""
mm8 = mm6 with the ladder ungated (budget raise still $10-only).

Pre-registered:
  P1 $10 IDENTITY: both gates behave as in mm6 -> byte-identical on $10 books.
  P2 $20/$40 LADDER FIRES then disarms against tight fields (self-limiting).
  P3 $20/$40 RANK: mm8 >= mm6 on visible-like AND held-out rosters.
  P4 TC13-LIKE (Lattice-ish 3-bot $20): our PnL must not fall -- $0.11 cushion.
     Reported as a distribution, since the live cushion is knife-edge.
  P5 RUIN: none.
"""
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arena2  # noqa: E402
from arena2 import (FixedWidthBot, FlowConfig, StalemateBot, draw_params,  # noqa: E402
                    run_session)
from audit_adversary import Adaptive, Aggressor, Sniper  # noqa: E402
import Market_Maker_2 as MM2  # noqa: E402
import Market_Maker_6 as MM6  # noqa: E402
import Market_Maker_8 as MM8  # noqa: E402

for _m in (MM6, MM8):
    _m.OrderType = MM2.OrderType
    _m.FokOrder = MM2.FokOrder
    _m.BinaryOption = MM2.BinaryOption
    _m.Underlying = MM2.Underlying
    _m.MarketHistory = MM2.MarketHistory

CAL = FlowConfig("neutral", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)
SHARP = FlowConfig("sharp", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)
W = {"fw05": .05, "fw10": .10, "fw25": .25}
_made: list = []


class Spy8(MM8.MarketMaker):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _made.append(self)


def field(names, mp, cap):
    out = []
    for n in names:
        if n == "stale":
            out.append(StalemateBot())
        elif n == "sniper":
            out.append(Sniper(mp, cap))
        elif n == "aggr":
            out.append(Aggressor(mp, cap))
        elif n == "adapt":
            out.append(Adaptive(mp, cap))
        else:
            out.append(FixedWidthBot(f"FW{n[2:]}", mp, W[n], 60))
    return out


def run(mod, names, cap, seed, flow=CAL):
    arena2.MarketMaker = Spy8 if mod is MM8 else mod.MarketMaker
    rng = random.Random(seed)
    mp = draw_params(rng)
    return run_session(mp, flow, field(names, mp, cap), cap, seed)


def main() -> int:
    fails = 0

    print("P1  $10 IDENTITY vs mm6")
    bad = tot = 0
    for names in (["stale"], ["fw25", "stale"], ["fw10", "stale"], ["fw05"]):
        for s in range(30):
            _, a = run(MM6, names, 10.0, 810_000 + s)
            _made.clear()
            _, b = run(MM8, names, 10.0, 810_000 + s)
            tot += 1
            bad += any(abs(a[k] - b[k]) > 1e-9 for k in a)
    print(f"    mismatches: {bad}/{tot}" + ("   *** FAIL" if bad else "   PASS"))
    fails += bad > 0

    print("\nP2/P3  $20 and $40: ladder behaviour and RANK")
    print(f"    {'roster':<22}{'cap':>5}{'mm6':>8}{'mm8':>8}{'d':>7}"
          f"{'armed@end':>11}{'our PnL d':>11}")
    for cap in (20.0, 40.0):
        for names in (["fw10", "stale"], ["fw05"], ["fw05", "fw10"],
                      ["sniper", "stale"], ["adapt"]):
            s6, s8, dp, armed = [], [], [], 0
            for s in range(40):
                a_sc, a = run(MM6, names, cap, 820_000 + s)
                _made.clear()
                b_sc, b = run(MM8, names, cap, 820_000 + s)
                s6.append(a_sc)
                s8.append(b_sc)
                dp.append(b["Hamza Khan"] - a["Hamza Khan"])
                armed += _made[-1]._sweep_on
            m6, m8 = statistics.fmean(s6), statistics.fmean(s8)
            print(f"    {'+'.join(names):<22}{cap:>5.0f}{m6:>8.3f}{m8:>8.3f}"
                  f"{m8 - m6:>+7.3f}{armed:>8}/40{statistics.fmean(dp):>+11.2f}")

    print("\nP4  TC13-LIKE 3-bot $20 (knife-edge $0.11 cushion live)")
    d, worse = [], 0
    for s in range(120):
        _, a = run(MM6, ["fw10", "fw05", "fw25"], 20.0, 830_000 + s)
        _made.clear()
        _, b = run(MM8, ["fw10", "fw05", "fw25"], 20.0, 830_000 + s)
        delta = b["Hamza Khan"] - a["Hamza Khan"]
        d.append(delta)
        worse += delta < 0
    d.sort()
    print(f"    PnL delta: mean {statistics.fmean(d):+.2f}  median {d[60]:+.2f}  "
          f"p10 {d[12]:+.2f}  p90 {d[108]:+.2f}")
    print(f"    sessions where mm8 is WORSE: {worse}/120 ({worse / 120:.0%})")
    print(f"    => live TC13 flip risk is ~{worse / 120:.0%} on a $0.11 cushion")

    print("\nP5  RUIN, all books, sharp flow")
    ruin = 0
    for cap in (10.0, 20.0, 40.0):
        for s in range(40):
            sc, _ = run(MM8, ["fw05", "stale"], cap, 840_000 + s, SHARP)
            ruin += sc == 0.0
    print(f"    bankruptcies: {ruin}/120" + ("   PASS" if ruin == 0 else "   *** FAIL"))
    fails += ruin > 0

    print("\n" + ("REJECT" if fails else "no hard failure -- decision is P3/P4 tradeoff"))
    return fails


if __name__ == "__main__":
    sys.exit(main())
