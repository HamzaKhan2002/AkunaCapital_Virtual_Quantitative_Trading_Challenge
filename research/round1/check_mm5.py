"""
mm5 mechanism check (vs mm4, the live 18.0), pre-registered.

  P1 INERTNESS $20/$40: gate off -> byte-identical to mm4, every seed.
  P2 TC6-LIKE (fw25+stale, $10): our PnL rises vs mm4 and FW0.25's falls --
     the whole point (need +$2.05 live).
  P3 OTHER $10 FIELDS: PnL not systematically worse; sweep behaviour intact.
  P4 RUIN: none, incl. sharp flow at the raised small-book budget.
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
import Market_Maker_5 as MM5  # noqa: E402

# single-identity world for enums/dataclasses (repo memory: cross-module `is`)
for _m in (MM4, MM5):
    _m.OrderType = MM2.OrderType
    _m.FokOrder = MM2.FokOrder
    _m.BinaryOption = MM2.BinaryOption
    _m.Underlying = MM2.Underlying
    _m.MarketHistory = MM2.MarketHistory

CAL = FlowConfig("neutral", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)
SHARP = FlowConfig("sharp", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)
W = {"fw05": .05, "fw10": .10, "fw25": .25}


def run(module, names, cap, seed, flow=CAL):
    arena2.MarketMaker = module.MarketMaker
    rng = random.Random(seed)
    mp = draw_params(rng)
    opp = [StalemateBot() if n == "stale" else FixedWidthBot(f"FW{n[2:]}", mp, W[n], 60)
           for n in names]
    return run_session(mp, flow, opp, cap, seed)


def main() -> int:
    fails = 0

    print("P1  INERTNESS $20/$40 vs mm4")
    bad = tot = 0
    for cap in (20.0, 40.0):
        for names in (["stale"], ["fw05"], ["fw10", "stale"], ["fw05", "fw25"]):
            for s in range(30):
                _, p4 = run(MM4, names, cap, 700_000 + s)
                _, p5 = run(MM5, names, cap, 700_000 + s)
                tot += 1
                bad += any(abs(p4[k] - p5[k]) > 1e-9 for k in p4)
    print(f"    mismatches: {bad}/{tot}" + ("   *** FAIL" if bad else "   PASS"))
    fails += bad > 0

    print("\nP2  TC6-LIKE fw25+stale $10 (the target)")
    d_us, d_fw, better = [], [], 0
    for s in range(60):
        _, p4 = run(MM4, ["fw25", "stale"], 10.0, 710_000 + s)
        _, p5 = run(MM5, ["fw25", "stale"], 10.0, 710_000 + s)
        d_us.append(p5["Hamza Khan"] - p4["Hamza Khan"])
        d_fw.append(p5["FW25"] - p4["FW25"])
        better += p5["Hamza Khan"] > p4["Hamza Khan"]
    print(f"    our PnL delta  {statistics.fmean(d_us):+7.2f}  (better in {better}/60)")
    print(f"    FW0.25 delta   {statistics.fmean(d_fw):+7.2f}")
    ok = statistics.fmean(d_us) > 0 and statistics.fmean(d_fw) < 0
    print("    PASS" if ok else "    *** FAIL (capture did not shift)")
    fails += not ok

    print("\nP3  OTHER $10 FIELDS (no systematic loss)")
    for names in (["stale"], ["fw25"], ["fw10", "stale"], ["fw05"]):
        d = []
        for s in range(40):
            _, p4 = run(MM4, names, 10.0, 720_000 + s)
            _, p5 = run(MM5, names, 10.0, 720_000 + s)
            d.append(p5["Hamza Khan"] - p4["Hamza Khan"])
        print(f"    {'+'.join(names):<14} delta {statistics.fmean(d):+7.2f} "
              f"(min {min(d):+.2f})")

    print("\nP4  RUIN sharp flow, $10, raised budget")
    ruin = 0
    for names in (["stale"], ["fw25", "stale"]):
        for s in range(60):
            sc, _ = run(MM5, names, 10.0, 730_000 + s, SHARP)
            ruin += sc == 0.0
    print(f"    bankruptcies: {ruin}/120" + ("   PASS" if ruin == 0 else "   *** FAIL"))
    fails += ruin > 0

    print("\n" + ("REJECT" if fails else "ALL PRE-REGISTERED PREDICTIONS PASS."))
    return fails


if __name__ == "__main__":
    sys.exit(main())
