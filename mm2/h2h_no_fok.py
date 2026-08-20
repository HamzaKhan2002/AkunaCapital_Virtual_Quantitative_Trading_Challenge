"""Is prev-gen's head-to-head win real (RFQ-side) or a FOK-flow artifact?

Decisive test: rerun the duel with the FOK channel turned OFF (fok_per_day=0).
RFQ competition is mechanical -- best price wins, ties split -- and does not
depend on any invented donation rate, so it is the arena dimension we can trust.
If prev still dominates without FOKs, the weakness is real and matters for a
Round-2 field of strong bots. If the gap collapses, it was the arena's invented
FOK donations (E53) and says nothing about live play.

Also reports PnL per channel so the source of the gap is explicit, not inferred.
"""
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arena2  # noqa: E402
from arena2 import FlowConfig, FixedWidthBot, StalemateBot, draw_params, run_session  # noqa: E402
from head_to_head import OldBotAdapter, load_old_bot  # noqa: E402
from Market_Maker_2 import Underlying as U2  # noqa: E402


def duel(mod, flow_cfg, n, extra_names, label):
    we = they = tie = 0
    ours_l, theirs_l = [], []
    for s in range(n):
        rng = random.Random(70000 + s)
        mp = draw_params(rng)
        rng2 = random.Random(70000 + s)
        _ = draw_params(rng2)
        v = {1: max(round(rng2.uniform(0.5, 5.0) * 4) / 4, 0.0),
             2: round(rng2.uniform(400, 1500), 2), 3: round(rng2.uniform(400, 1500), 2)}
        unds = [U2("FED", 1, v[1]), U2("AJR", 2, v[2]), U2("THR", 3, v[3])]
        opps = [OldBotAdapter(unds, [], 20.0, mod)]
        for nm in extra_names:
            opps.append(StalemateBot() if nm == "stale"
                        else FixedWidthBot(f"Fixed Width {arena2.WIDTH[nm]}", mp, arena2.WIDTH[nm]))
        _, pnl = run_session(mp, flow_cfg, opps, 20.0, seed=70000 + s)
        o, t = pnl.get("Hamza Khan", 0.0), pnl.get("MM-prev (v9)", 0.0)
        ours_l.append(o)
        theirs_l.append(t)
        if o > t + 1e-9:
            we += 1
        elif t > o + 1e-9:
            they += 1
        else:
            tie += 1
    print(f"  {label:>34}: mm2 {we:>2}/{n}  prev {they:>2}  tie {tie:>2} | "
          f"mean PnL mm2 {statistics.fmean(ours_l):+8.2f}  prev {statistics.fmean(theirs_l):+8.2f}")
    return we, they


def main():
    mod = load_old_bot()
    n = 60
    print("DECISIVE TEST: does prev-gen's advantage survive without the FOK channel?\n")

    print("WITH FOKs (the original head-to-head result):")
    duel(mod, FlowConfig("neutral", 4, 2, 12), n, [], "duel, neutral flow, FOKs ON")
    duel(mod, FlowConfig("sharp", 4, 3, 12), n, [], "duel, sharp flow, FOKs ON")

    print("\nFOKs DISABLED (fok_per_day=0) -- pure RFQ competition, no invented donations:")
    duel(mod, FlowConfig("neutral", 4, 0, 12), n, [], "duel, RFQ only")
    duel(mod, FlowConfig("sharp", 4, 0, 12), n, [], "duel, RFQ only (sharp)")
    duel(mod, FlowConfig("neutral", 4, 0, 12), n, ["fw05", "fw10"], "RFQ only + FW05 + FW10")

    print("\nIf prev's dominance vanishes with FOKs off, the head-to-head was an artifact")
    print("of the arena's invented FOK donation rate and carries no Round-2 implication.")


if __name__ == "__main__":
    main()
