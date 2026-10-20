"""Calibrate arena flow to the VERBOSE logs, then re-run the duel at realistic volume.

Real flow, counted from the only sessions the grader prints in full:
  TC2: 2 RFQ + 1 FOK over 3 days
  TC3: 2 RFQ + 3 FOK over 4 days
  TC4: 1 RFQ + 6 FOK over 4 days
=> roughly 0.5 RFQ/day and 1 FOK/day, order sizes 2-26 lots.
The arena was running 4 RFQ/day + 2 FOK/day with big-order draws to 200 -- roughly
an order of magnitude too much flow, which is exactly the regime where a bot sizing
at 60% of margin (prev-gen) dominates one sizing at 25% (mm2).
"""
import os
import random
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arena2  # noqa: E402
from arena2 import FlowConfig, StalemateBot, draw_params, run_session  # noqa: E402
from head_to_head import OldBotAdapter, load_old_bot  # noqa: E402
from Market_Maker_2 import Underlying as U2  # noqa: E402

# ---- count the real flow straight from the VERBOSE logs
txt = open(os.path.join(os.path.dirname(__file__), "Compiler_Messages_Run_12.txt"),
           encoding="utf-8", errors="ignore").read()
for tc in (2, 3, 4):
    m = re.search(rf"Test Case {tc}:(.*?)(?=Test Case {tc + 1}:)", txt, re.S)
    body = m.group(1)
    print(f"  TC{tc}: {len(re.findall(r'RFQ from', body))} RFQ, "
          f"{len(re.findall(r'FOK from', body))} FOK, "
          f"{len(re.findall(r'advanced by one step', body))} day advances")

CONFIGS = {
    "arena default (4 RFQ, 2 FOK/day)": FlowConfig("neutral", 4, 2, 12),
    "realistic (1 RFQ, 1 FOK/day)": FlowConfig("neutral", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60),
    "realistic, no big orders": FlowConfig("neutral", 1, 1, 12, big_order_prob=0.0, big_qty_hi=12),
}


def duel(mod, cfg, n=60):
    we = they = 0
    ours, theirs, stale = [], [], []
    for s in range(n):
        rng = random.Random(70000 + s)
        mp = draw_params(rng)
        rng2 = random.Random(70000 + s)
        _ = draw_params(rng2)
        v = {1: max(round(rng2.uniform(0.5, 5.0) * 4) / 4, 0.0),
             2: round(rng2.uniform(400, 1500), 2), 3: round(rng2.uniform(400, 1500), 2)}
        unds = [U2("FED", 1, v[1]), U2("AJR", 2, v[2]), U2("THR", 3, v[3])]
        opps = [OldBotAdapter(unds, [], 10.0, mod), StalemateBot()]
        _, pnl = run_session(mp, cfg, opps, 10.0, seed=70000 + s)
        o, t = pnl.get("Hamza Khan", 0.0), pnl.get("MM-prev (v9)", 0.0)
        ours.append(o)
        theirs.append(t)
        stale.append(pnl.get("Stalemate Quoter", 0.0))
        we += o > t + 1e-9
        they += t > o + 1e-9
    return we, they, statistics.fmean(ours), statistics.fmean(theirs), statistics.fmean(stale)


def main():
    mod = load_old_bot()
    print("real flow counted from VERBOSE logs:")
    print()
    print("$10 book, us vs prev-gen vs Stalemate (live TC5 reference: Stalemate +30, us +3.65)\n")
    print(f"{'flow config':>34}{'mm2 wins':>10}{'prev wins':>11}{'mm2 PnL':>10}"
          f"{'prev PnL':>10}{'Stale PnL':>11}")
    for label, cfg in CONFIGS.items():
        we, they, o, t, st = duel(mod, cfg)
        print(f"{label:>34}{we:>10}{they:>11}{o:>+10.2f}{t:>+10.2f}{st:>+11.2f}")
    print("\nThe config whose Stalemate PnL lands near the live +30 is the calibrated one;")
    print("read the duel result ONLY from that row.")


if __name__ == "__main__":
    main()
