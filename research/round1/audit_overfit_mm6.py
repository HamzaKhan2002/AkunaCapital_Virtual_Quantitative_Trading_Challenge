"""
Overfit audit of mm6 (18.3). Two suspects, both fitted against the VISIBLE suite:

  S1  SWEEP_CAPITAL_MAX = 10.5   -- chosen to include $10 books and exclude $20
                                    specifically to protect TC13's $0.11 cushion.
  S2  QUOTE_LOCK_SMALL 0.80/0.70 -- reached by SUBMITTING until TC6 flipped
      MAX_LOCKED_SMALL 0.80         (two live doses). Textbook fitting risk.
  S3  SWEEP_BID/OFFER 0.05/0.95  -- derived offline (E56), never live-tuned.

The discriminating question for each: PLATEAU or PEAK?
  plateau -> the exact value is not load-bearing; the MECHANISM carries it
  peak    -> we fitted noise on 5 visible $10 tests and it will not transfer

Plus a held-out check: rosters that appear NOWHERE in the visible suite,
including the competent adversaries from audit_adversary.py.
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

for _m in (MM6,):
    _m.OrderType = MM2.OrderType
    _m.FokOrder = MM2.FokOrder
    _m.BinaryOption = MM2.BinaryOption
    _m.Underlying = MM2.Underlying
    _m.MarketHistory = MM2.MarketHistory

CAL = FlowConfig("neutral", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)
W = {"fw05": .05, "fw10": .10, "fw25": .25}
N = 40

VISIBLE = [["stale"], ["fw25", "stale"], ["fw25"], ["fw10", "stale"], ["fw10", "fw25"]]
HELDOUT = [["fw05"], ["fw05", "stale"], ["fw05", "fw25"], ["fw10"],
           ["fw05", "fw10", "stale"], ["fw10", "fw25", "stale"]]


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


def score_over(rosters, cap=10.0, seeds=N):
    tot = []
    for names in rosters:
        for s in range(seeds):
            arena2.MarketMaker = MM6.MarketMaker
            rng = random.Random(880_000 + s)
            mp = draw_params(rng)
            sc, _ = run_session(mp, CAL, field(names, mp, cap), cap, 880_000 + s)
            tot.append(sc)
    return statistics.fmean(tot)


def main() -> int:
    base_q = MM6.MarketMaker.QUOTE_LOCK_SMALL
    base_m = MM6.MarketMaker.MAX_LOCKED_SMALL
    base_b = MM6.MarketMaker.SWEEP_BID

    print("=" * 72)
    print("S2  BUDGET FRACTION: plateau or peak?  (mean rank score, $10 books)")
    print("=" * 72)
    print(f"{'UNKNOWN frac':>13}{'visible':>10}{'HELD-OUT':>10}{'both':>9}")
    rows = []
    for f in (0.25, 0.35, 0.50, 0.60, 0.70, 0.80, 0.90):
        MM6.MarketMaker.QUOTE_LOCK_SMALL = {"UNINF": min(f + .10, .95),
                                            "UNKNOWN": f, "INFORMED": 0.02}
        v = score_over(VISIBLE)
        h = score_over(HELDOUT)
        rows.append((f, v, h))
        mark = "  <-- shipped" if abs(f - 0.70) < 1e-9 else ""
        print(f"{f:>13.2f}{v:>10.3f}{h:>10.3f}{(v + h) / 2:>9.3f}{mark}")
    MM6.MarketMaker.QUOTE_LOCK_SMALL = base_q
    spread_v = max(r[1] for r in rows) - min(r[1] for r in rows)
    spread_h = max(r[2] for r in rows) - min(r[2] for r in rows)
    best_h = max(rows, key=lambda r: r[2])[0]
    print(f"\n   visible  range across fracs: {spread_v:.3f}")
    print(f"   held-out range across fracs: {spread_h:.3f}")
    print(f"   held-out optimum at frac {best_h:.2f} (shipped 0.70)")

    print("\n" + "=" * 72)
    print("S1  GATE BOUNDARY: is $10.5 a cliff?  (mean score by book size)")
    print("=" * 72)
    print(f"{'capital':>9}{'gate':>7}{'visible':>10}{'HELD-OUT':>10}")
    for cap in (8.0, 10.0, 10.4, 12.0, 20.0):
        on = cap <= MM6.MarketMaker.SWEEP_CAPITAL_MAX
        v = score_over(VISIBLE, cap=cap, seeds=25)
        h = score_over(HELDOUT, cap=cap, seeds=25)
        print(f"{cap:>9.1f}{'ON' if on else 'off':>7}{v:>10.3f}{h:>10.3f}")

    print("\n" + "=" * 72)
    print("S3  SWEEP PRICE: plateau or peak?  ($10, both roster sets)")
    print("=" * 72)
    print(f"{'sweep bid':>11}{'visible':>10}{'HELD-OUT':>10}")
    for b in (0.01, 0.03, 0.05, 0.08, 0.12):
        MM6.MarketMaker.SWEEP_BID = b
        MM6.MarketMaker.SWEEP_OFFER = round(1.0 - b, 2)
        v = score_over(VISIBLE, seeds=25)
        h = score_over(HELDOUT, seeds=25)
        mark = "  <-- shipped" if abs(b - 0.05) < 1e-9 else ""
        print(f"{b:>11.2f}{v:>10.3f}{h:>10.3f}{mark}")
    MM6.MarketMaker.SWEEP_BID = base_b
    MM6.MarketMaker.SWEEP_OFFER = 0.95

    print("\n" + "=" * 72)
    print("HELD-OUT vs COMPETENT ADVERSARIES ($10, never in the visible suite)")
    print("=" * 72)
    for names in (["sniper"], ["aggr"], ["adapt"], ["sniper", "stale"],
                  ["aggr", "adapt", "stale"]):
        sc2, sc6 = [], []
        for s in range(N):
            for mod, acc in ((MM2, sc2), (MM6, sc6)):
                arena2.MarketMaker = mod.MarketMaker
                rng = random.Random(890_000 + s)
                mp = draw_params(rng)
                sc, _ = run_session(mp, CAL, field(names, mp, 10.0), 10.0, 890_000 + s)
                acc.append(sc)
        a, b = statistics.fmean(sc2), statistics.fmean(sc6)
        print(f"   {'+'.join(names):<22} mm2 {a:.3f}  ->  mm6 {b:.3f}   {b - a:+.3f}")
    MM6.MarketMaker.MAX_LOCKED_SMALL = base_m
    return 0


if __name__ == "__main__":
    sys.exit(main())
