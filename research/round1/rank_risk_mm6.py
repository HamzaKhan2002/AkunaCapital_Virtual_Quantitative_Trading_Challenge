"""Rank-flip risk of mm6's fatter tails vs mm4, seed-paired, 200 seeds/roster."""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arena2  # noqa: E402
from arena2 import FixedWidthBot, FlowConfig, StalemateBot, draw_params, run_session  # noqa: E402
import Market_Maker_2 as MM2  # noqa: E402
import Market_Maker_4 as MM4  # noqa: E402
import Market_Maker_6 as MM6  # noqa: E402

for m in (MM4, MM6):
    m.OrderType = MM2.OrderType
    m.FokOrder = MM2.FokOrder
    m.BinaryOption = MM2.BinaryOption
    m.Underlying = MM2.Underlying
    m.MarketHistory = MM2.MarketHistory

CAL = FlowConfig("neutral", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)
W = {"fw05": .05, "fw10": .10, "fw25": .25}


def run(mod, names, seed):
    arena2.MarketMaker = mod.MarketMaker
    rng = random.Random(seed)
    mp = draw_params(rng)
    opp = [StalemateBot() if n == "stale"
           else FixedWidthBot(f"FW{n[2:]}", mp, W[n], 60) for n in names]
    _, p = run_session(mp, CAL, opp, 10.0, seed)
    return p


print(f"{'roster':<14}{'mm4 losses':>11}{'mm6 losses':>11}{'mm6 worst margin':>18}"
      f"   (200 seeds, rank vs best rival)")
for names in (["fw25"], ["fw10", "stale"], ["fw05"], ["fw25", "stale"], ["stale"]):
    l4 = l6 = 0
    worst = 1e9
    for s in range(200):
        p4 = run(MM4, names, 740_000 + s)
        p6 = run(MM6, names, 740_000 + s)
        r4 = max(v for k, v in p4.items() if k != "Hamza Khan")
        r6 = max(v for k, v in p6.items() if k != "Hamza Khan")
        l4 += p4["Hamza Khan"] <= r4
        l6 += p6["Hamza Khan"] <= r6
        worst = min(worst, p6["Hamza Khan"] - r6)
    print(f"{'+'.join(names):<14}{l4:>11}{l6:>11}{worst:>18.2f}")
