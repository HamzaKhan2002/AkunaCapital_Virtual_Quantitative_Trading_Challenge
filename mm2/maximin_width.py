"""
Game theory, done as a computation rather than an intuition.

We cannot identify the opponent in-session (probe falsified by spillover;
passive fill signal has no contrast; classifier starved at median 2 obs/cp).
So "know your opponent, then best-respond" is closed.

What is NOT closed is the robust version: pick the strategy that maximises the
WORST CASE over the whole opponent set. Every sweep so far optimised the mean,
which is the wrong criterion for an unknown round-2 field.

This also settles the reviewer's standing charge that BASE_EDGE=3.5c is "an
empirical compromise between two known competitor widths". If 3.5c turns out to
be the maximin width over a zoo that includes opponents it was never tuned
against, then it is derived, not fitted.

Opponent zoo (7 singles + 3 mixed):
  Stalemate 0.00/1.00        the only thing that beats us live
  FW 0.05 / 0.10 / 0.25      the visible archetypes
  Sniper 1c                  competent, margin-disciplined  (unseen in round 1)
  Aggressor 2c               competent, no margin discipline (unseen)
  Adaptive                   reactive width                  (unseen)
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
import Market_Maker_2 as MM  # noqa: E402

CAL = FlowConfig("neutral", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)
N = 30
CAPS = (10.0, 20.0, 40.0)

ZOO = {
    "Stalemate":   lambda mp, c: [StalemateBot()],
    "FW 0.05":     lambda mp, c: [FixedWidthBot("FW05", mp, 0.05)],
    "FW 0.10":     lambda mp, c: [FixedWidthBot("FW10", mp, 0.10)],
    "FW 0.25":     lambda mp, c: [FixedWidthBot("FW25", mp, 0.25)],
    "Sniper 1c":   lambda mp, c: [Sniper(mp, c)],
    "Aggressor":   lambda mp, c: [Aggressor(mp, c)],
    "Adaptive":    lambda mp, c: [Adaptive(mp, c)],
    "FW05+Stale":  lambda mp, c: [FixedWidthBot("FW05", mp, 0.05), StalemateBot()],
    "Snipe+Aggr":  lambda mp, c: [Sniper(mp, c), Aggressor(mp, c)],
    "3-bot mixed": lambda mp, c: [Sniper(mp, c), FixedWidthBot("FW05", mp, 0.05),
                                  StalemateBot()],
}

EDGES = (0.020, 0.025, 0.030, 0.035, 0.040, 0.050, 0.065, 0.080)


def main() -> int:
    arena2.MarketMaker = MM.MarketMaker
    base = MM.MarketMaker.BASE_EDGE
    table = {}
    for e in EDGES:
        MM.MarketMaker.BASE_EDGE = {"UNINF": e - 0.005, "UNKNOWN": e,
                                    "INFORMED": max(0.12, e * 3)}
        row = {}
        for name, fn in ZOO.items():
            sc = []
            for cap in CAPS:
                for s in range(N):
                    rng = random.Random(770_000 + s)
                    mp = draw_params(rng)
                    score, _ = run_session(mp, CAL, fn(mp, cap), cap, 770_000 + s)
                    sc.append(score)
            row[name] = statistics.fmean(sc)
        table[e] = row
    MM.MarketMaker.BASE_EDGE = base

    print(f"rank score by our BASE_EDGE vs each opponent "
          f"({N} seeds x {len(CAPS)} capitals per cell)\n")
    print(f"{'edge':>6}" + "".join(f"{n[:10]:>12}" for n in ZOO) + f"{'MEAN':>8}{'MIN':>8}")
    for e in EDGES:
        r = table[e]
        vals = list(r.values())
        mark = "  <-- shipped" if abs(e - 0.035) < 1e-9 else ""
        print(f"{e * 100:>5.1f}c" + "".join(f"{r[n]:>12.3f}" for n in ZOO)
              + f"{statistics.fmean(vals):>8.3f}{min(vals):>8.3f}{mark}")

    best_mean = max(EDGES, key=lambda e: statistics.fmean(table[e].values()))
    best_min = max(EDGES, key=lambda e: min(table[e].values()))
    print(f"\n  mean-optimal   : {best_mean * 100:.1f}c "
          f"(mean {statistics.fmean(table[best_mean].values()):.3f})")
    print(f"  MAXIMIN-optimal: {best_min * 100:.1f}c "
          f"(worst case {min(table[best_min].values()):.3f})")
    print(f"  shipped 3.5c   : mean {statistics.fmean(table[0.035].values()):.3f}, "
          f"worst case {min(table[0.035].values()):.3f}")

    print("\n  worst-case opponent at each width (who holds us down):")
    for e in EDGES:
        w = min(table[e], key=table[e].get)
        print(f"     {e * 100:>4.1f}c -> {w} ({table[e][w]:.3f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
