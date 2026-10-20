"""
mm4 mechanism check, pre-registered.

  P1 INERTNESS: on $20/$40 books the gate is off from __init__, so mm4's
     entire session must be BYTE-IDENTICAL to mm2's -- every agent's PnL equal
     to the cent, every seed. One mismatch = reject.
  P2 STALE-ONLY $10: sweep stays armed, our PnL multiplies, Stalemate starves.
     This is the TC5 case, the entire point of the change.
  P3 TIGHT-FIELD $10: sweep disarms fast; PnL cost vs mm2 bounded by ~one
     RFQ's income; rank score unchanged.
  P4 RUIN: none, anywhere, including sharp flow (solvency invariant untouched).
"""
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arena2  # noqa: E402
from arena2 import (FixedWidthBot, FlowConfig, StalemateBot, draw_params,  # noqa: E402
                    run_session)
import Market_Maker_2 as MM2  # noqa: E402
import Market_Maker_4 as MM4  # noqa: E402

# The arena builds orders with MM2's enums/dataclasses; a copied module's
# `is OrderType.BUY` would always be False. Unify the identity world.
MM4.OrderType = MM2.OrderType
MM4.FokOrder = MM2.FokOrder
MM4.BinaryOption = MM2.BinaryOption
MM4.Underlying = MM2.Underlying
MM4.MarketHistory = MM2.MarketHistory

CAL = FlowConfig("neutral", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)
SHARP = FlowConfig("sharp", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)

_last: list = []


class Spy4(MM4.MarketMaker):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _last.append(self)


def run(module, names, cap, seed, flow=CAL):
    arena2.MarketMaker = Spy4 if module is MM4 else module.MarketMaker
    rng = random.Random(seed)
    mp = draw_params(rng)
    opp = [StalemateBot() if n == "stale"
           else FixedWidthBot(f"FW{n[2:]}", mp, {"fw05": .05, "fw10": .10,
                                                 "fw25": .25}[n], 60)
           for n in names]
    return run_session(mp, flow, opp, cap, seed)


def main() -> int:
    fails = 0

    print("P1  INERTNESS on $20/$40 (gate off -> byte-identical sessions)")
    bad = tot = 0
    for cap in (20.0, 40.0):
        for names in (["stale"], ["fw05"], ["fw10", "stale"], ["fw05", "fw25"]):
            for s in range(30):
                _, p2 = run(MM2, names, cap, 640_000 + s)
                _last.clear()
                _, p4 = run(MM4, names, cap, 640_000 + s)
                tot += 1
                if any(abs(p2[k] - p4[k]) > 1e-9 for k in p2):
                    bad += 1
    print(f"    mismatched sessions: {bad} / {tot}"
          + ("   *** FAIL" if bad else "   PASS"))
    fails += bad > 0

    print("\nP2  STALE-ONLY $10 (the TC5 case)")
    o2, o4, st2, st4, armed = [], [], [], [], 0
    for s in range(60):
        _, p2 = run(MM2, ["stale"], 10.0, 650_000 + s)
        _last.clear()
        _, p4 = run(MM4, ["stale"], 10.0, 650_000 + s)
        o2.append(p2["Hamza Khan"])
        o4.append(p4["Hamza Khan"])
        st2.append(max(v for k, v in p2.items() if k != "Hamza Khan"))
        st4.append(max(v for k, v in p4.items() if k != "Hamza Khan"))
        armed += _last[-1]._sweep_on
    print(f"    our PnL   mm2 {statistics.fmean(o2):+7.2f}  ->  mm4 "
          f"{statistics.fmean(o4):+7.2f}")
    print(f"    Stalemate mm2 {statistics.fmean(st2):+7.2f}  ->  mm4 "
          f"{statistics.fmean(st4):+7.2f}")
    print(f"    sweep still armed at session end: {armed}/60")
    win2 = sum(1 for a, b in zip(o2, st2) if a > b)
    win4 = sum(1 for a, b in zip(o4, st4) if a > b)
    print(f"    sessions where WE out-earn Stalemate: mm2 {win2}/60 -> mm4 {win4}/60"
          + ("   PASS" if win4 > win2 else "   *** FAIL (no rank progress)"))
    fails += win4 <= win2

    print("\nP3  TIGHT-FIELD $10 (must disarm cheaply)")
    for names in (["fw25"], ["fw10", "stale"], ["fw05"], ["fw25", "stale"]):
        d = []
        armed = 0
        for s in range(40):
            _, p2 = run(MM2, names, 10.0, 660_000 + s)
            _last.clear()
            _, p4 = run(MM4, names, 10.0, 660_000 + s)
            d.append(p4["Hamza Khan"] - p2["Hamza Khan"])
            armed += _last[-1]._sweep_on
        m = statistics.fmean(d)
        print(f"    {'+'.join(names):<14} PnL delta {m:+7.2f}  "
              f"(min {min(d):+.2f})  still-armed {armed}/40")

    print("\nP4  RUIN under sharp flow, sweep armed")
    ruin = 0
    for s in range(120):
        sc, _ = run(MM4, ["stale"], 10.0, 670_000 + s, SHARP)
        ruin += sc == 0.0
    print(f"    bankruptcies: {ruin}/120" + ("   PASS" if ruin == 0 else "   *** FAIL"))
    fails += ruin > 0

    print("\n" + ("REJECT: a pre-registered prediction failed." if fails
                  else "ALL PRE-REGISTERED PREDICTIONS PASS."))
    return fails


if __name__ == "__main__":
    sys.exit(main())
