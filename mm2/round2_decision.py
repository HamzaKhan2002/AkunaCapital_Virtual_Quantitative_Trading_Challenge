"""
THE ROUND-2 DECISION, measured.

round2_peers.py found the one field where mm6 collapses: peers that run an
UNGATED extreme-price ladder at $20+, where ours is switched off ($10.5 gate).
We score 0.484 there -- barely above the 0.4 floor.

mm8 is mm6 with the ladder ungated (budget raise still $10-only). It cost a
MEASURED -0.4 in round 1 (TC16). The question is whether it buys back more than
that against ladder-equipped peers in round 2.

Same code serves both rounds, so this is a single joint decision.
"""
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arena2  # noqa: E402
from arena2 import FlowConfig, draw_params, run_session  # noqa: E402
from audit_adversary import Adaptive, Sniper  # noqa: E402
from round2_peers import Peer  # noqa: E402
import Market_Maker_2 as MM2  # noqa: E402
import Market_Maker_6 as MM6  # noqa: E402
import Market_Maker_8 as MM8  # noqa: E402

for _m in (MM6, MM8):
    _m.OrderType = MM2.OrderType
    _m.FokOrder = MM2.FokOrder
    _m.BinaryOption = MM2.BinaryOption
    _m.Underlying = MM2.Underlying
    _m.MarketHistory = MM2.MarketHistory

N = 60
FLOW = FlowConfig("neutral", 4, 2, 12, big_order_prob=0.12, big_qty_hi=100)

FIELDS = {
    "peer-ladder x2": lambda mp, c: [Peer(mp, c, "P1-lad", ladder=True),
                                     Peer(mp, c, "P2-lad", ladder=True)],
    "2 peers + ladder": lambda mp, c: [Peer(mp, c, "P1"),
                                       Peer(mp, c, "P2-lad", ladder=True)],
    "all-star": lambda mp, c: [Peer(mp, c, "P-lad", ladder=True),
                               Peer(mp, c, "P-fat", frac=0.50), Sniper(mp, c)],
    "3 peers (tight)": lambda mp, c: [Peer(mp, c, "P1"), Peer(mp, c, "P2"),
                                      Peer(mp, c, "P3")],
    "sniper + adaptive": lambda mp, c: [Sniper(mp, c), Adaptive(mp, c)],
}


def score(mod, fn, cap):
    sc = []
    for s in range(N):
        arena2.MarketMaker = mod.MarketMaker
        rng = random.Random(980_000 + s)
        mp = draw_params(rng)
        v, _ = run_session(mp, FLOW, fn(mp, cap), cap, 980_000 + s)
        sc.append(v)
    return statistics.fmean(sc)


def main() -> int:
    print("mm6 (gated, SHIPPING 18.3)  vs  mm8 (ladder ungated, -0.4 in round 1)\n")
    print(f"{'field':<20}{'cap':>5}{'mm6':>8}{'mm8':>8}{'delta':>8}")
    d20p, all_d = [], []
    for label, fn in FIELDS.items():
        for cap in (10.0, 20.0, 40.0, 60.0):
            a, b = score(MM6, fn, cap), score(MM8, fn, cap)
            d = b - a
            all_d.append(d)
            if cap >= 20:
                d20p.append(d)
            flag = "  <-- the collapse" if (label == "peer-ladder x2"
                                            and cap == 20.0) else ""
            print(f"{label:<20}{cap:>5.0f}{a:>8.3f}{b:>8.3f}{d:>+8.3f}{flag}")

    m_all = statistics.fmean(all_d)
    m_20 = statistics.fmean(d20p)
    print(f"\n  mean delta, all cells        : {m_all:+.4f}")
    print(f"  mean delta, $20+ only        : {m_20:+.4f}")
    print(f"  implied over a 16-test round : {m_all * 16:+.2f} points")

    print("\n" + "=" * 66)
    print("DECISION")
    print("=" * 66)
    print(f"  round-1 cost of ungating : -0.40  (MEASURED live, TC16)")
    print(f"  round-2 gain of ungating : {m_all * 16:+.2f}  (arena, peers with ladders)")
    if m_all * 16 > 0.40:
        print("  => ungating pays for itself IF round 2 weighs like round 1.")
    else:
        print("  => ungating does NOT pay for itself. Keep mm6.")
    print("\n  Caveat that dominates both numbers: the arena has mispredicted live")
    print("  results 5 times (E53, E55, mm3, mm8/TC16, and its own rank inversion).")
    print("  The -0.40 is measured on the real grader; the round-2 gain is not.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
