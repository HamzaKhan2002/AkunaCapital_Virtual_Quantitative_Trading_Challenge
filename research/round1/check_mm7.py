"""
mm7 mechanism check (vs mm6, the live 18.3), pre-registered.

  P1 INERTNESS $10/$20: gate off -> byte-identical to mm6, every seed.
  P2 DETECTOR SEPARATION at $40 (the crux): fire-rate HIGH on donating (dumb)
     flow, ~ZERO on sharp flow. If sharp-flow fire-rate > 10%, KILL THE CHANGE
     -- a misfire in a TC19/TC20-like session forfeits held ranks.
  P3 TC18-LIKE (fw05 @ $40, dumb flow): we out-earn FW0.05 in more sessions
     than mm6 does. TC16-like: our PnL rises (cushion grows).
  P4 SHARP-FLOW $40: PnL ~= mm6 (detector silent => behaviour unchanged).
  P5 RUIN: none anywhere.
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
import Market_Maker_6 as MM6  # noqa: E402
import Market_Maker_7 as MM7  # noqa: E402

for _m in (MM6, MM7):
    _m.OrderType = MM2.OrderType
    _m.FokOrder = MM2.FokOrder
    _m.BinaryOption = MM2.BinaryOption
    _m.Underlying = MM2.Underlying
    _m.MarketHistory = MM2.MarketHistory

DUMB = FlowConfig("dumb", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)
CAL = FlowConfig("neutral", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)
SHARP = FlowConfig("sharp", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)
W = {"fw05": .05, "fw10": .10, "fw25": .25}

_made: list = []


class Spy7(MM7.MarketMaker):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _made.append(self)

    def fired(self):
        return (self._flow_n >= self.FLOW_GATE_MIN_OBS
                and self._flow_sum / self._flow_n >= self.FLOW_GATE_MEAN)


def run(module, names, cap, seed, flow=CAL):
    arena2.MarketMaker = Spy7 if module is MM7 else module.MarketMaker
    rng = random.Random(seed)
    mp = draw_params(rng)
    opp = [StalemateBot() if n == "stale" else FixedWidthBot(f"FW{n[2:]}", mp, W[n], 60)
           for n in names]
    return run_session(mp, flow, opp, cap, seed)


def main() -> int:
    fails = 0

    print("P1  INERTNESS $10/$20 vs mm6")
    bad = tot = 0
    for cap in (10.0, 20.0):
        for names in (["stale"], ["fw25", "stale"], ["fw05"], ["fw10", "stale"]):
            for s in range(30):
                _, p6 = run(MM6, names, cap, 760_000 + s)
                _made.clear()
                _, p7 = run(MM7, names, cap, 760_000 + s)
                tot += 1
                bad += any(abs(p6[k] - p7[k]) > 1e-9 for k in p6)
    print(f"    mismatches: {bad}/{tot}" + ("   *** FAIL" if bad else "   PASS"))
    fails += bad > 0

    print("\nP2  DETECTOR SEPARATION at $40 (fw05 roster)")
    rates = {}
    for label, flow in (("dumb", DUMB), ("neutral", CAL), ("sharp", SHARP)):
        fired = 0
        for s in range(60):
            _made.clear()
            run(MM7, ["fw05"], 40.0, 770_000 + s, flow)
            fired += _made[-1].fired()
        rates[label] = fired / 60
        print(f"    {label:<8} fire-rate {fired}/60 = {fired / 60:.0%}")
    if rates["sharp"] > 0.10:
        print("    *** FAIL: fires on sharp flow -- forfeits TC19/TC20-like ranks")
        fails += 1
    elif rates["dumb"] < 0.50:
        print("    *** FAIL: barely fires on donating flow -- mechanism dead weight")
        fails += 1
    else:
        print("    PASS")

    print("\nP3  TC18-LIKE fw05 $40 dumb flow (rank vs FW0.05)")
    w6 = w7 = 0
    d = []
    for s in range(60):
        _, p6 = run(MM6, ["fw05"], 40.0, 780_000 + s, DUMB)
        _made.clear()
        _, p7 = run(MM7, ["fw05"], 40.0, 780_000 + s, DUMB)
        w6 += p6["Hamza Khan"] > p6["FW05"]
        w7 += p7["Hamza Khan"] > p7["FW05"]
        d.append(p7["Hamza Khan"] - p6["Hamza Khan"])
    print(f"    beat FW0.05: mm6 {w6}/60 -> mm7 {w7}/60   (PnL delta "
          f"{statistics.fmean(d):+.2f})")
    if w7 <= w6:
        print("    *** FAIL: no rank progress where the mechanism should pay")
        fails += 1
    else:
        print("    PASS")

    print("\nP4  SHARP-FLOW $40 (must be ~inert)")
    d = []
    for s in range(40):
        _, p6 = run(MM6, ["fw05"], 40.0, 790_000 + s, SHARP)
        _made.clear()
        _, p7 = run(MM7, ["fw05"], 40.0, 790_000 + s, SHARP)
        d.append(p7["Hamza Khan"] - p6["Hamza Khan"])
    m = statistics.fmean(d)
    print(f"    PnL delta {m:+.2f} (min {min(d):+.2f})"
          + ("   PASS" if abs(m) < 1.0 else "   *** FAIL: not inert"))
    fails += abs(m) >= 1.0

    print("\nP5  RUIN $40, all flows")
    ruin = 0
    for flow in (DUMB, SHARP):
        for s in range(60):
            sc, _ = run(MM7, ["fw05"], 40.0, 800_000 + s, flow)
            ruin += sc == 0.0
    print(f"    bankruptcies: {ruin}/120" + ("   PASS" if ruin == 0 else "   *** FAIL"))
    fails += ruin > 0

    print("\n" + ("REJECT: a pre-registered prediction failed." if fails
                  else "ALL PRE-REGISTERED PREDICTIONS PASS."))
    return fails


if __name__ == "__main__":
    sys.exit(main())
