"""THE decisive comparison: mm2 vs prev-gen across the REAL roster distribution,
in shared sessions, scored by RANK (the actual objective) at CALIBRATED flow.

Calibration established in h2h_calibrated_flow.py: 1 RFQ + 1 FOK/day reproduces
live TC5 closely (our PnL +4.13 vs live +3.65; Stalemate +38.73 vs live +30).

The earlier duel used a Stalemate-only $10 roster = TC5-like, which is prev-gen's
single best session type (and one both bots lose anyway, 0.4 each). Here both bots
compete in the SAME session across all 8 fully-specified rosters, and we score by
rank -- which is what the competition actually pays, in Phase 1 and Round 2 alike.
"""
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arena2  # noqa: E402
from arena2 import KNOWN_TESTS, FlowConfig, FixedWidthBot, StalemateBot, draw_params, run_session  # noqa: E402
from head_to_head import OldBotAdapter, load_old_bot  # noqa: E402
from Market_Maker_2 import Underlying as U2  # noqa: E402

CAL = FlowConfig("neutral", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)


def main():
    mod = load_old_bot()
    n = 60
    print("both bots in the SAME session, calibrated flow, real roster distribution")
    print("score = 0.4 + 0.6 * (opponents out-earned / opponents), as the grader pays\n")
    print(f"{'test':>6}{'cap':>5}{'roster':>22}{'mm2 score':>11}{'prev score':>12}"
          f"{'mm2 PnL':>10}{'prev PnL':>10}")
    mm2_scores, prev_scores = [], []
    for tc, (cap, names, _actual) in KNOWN_TESTS.items():
        s_mm2, s_prev, p_mm2, p_prev = [], [], [], []
        for s in range(n):
            rng = random.Random(60000 + s)
            mp = draw_params(rng)
            rng2 = random.Random(60000 + s)
            _ = draw_params(rng2)
            v = {1: max(round(rng2.uniform(0.5, 5.0) * 4) / 4, 0.0),
                 2: round(rng2.uniform(400, 1500), 2), 3: round(rng2.uniform(400, 1500), 2)}
            unds = [U2("FED", 1, v[1]), U2("AJR", 2, v[2]), U2("THR", 3, v[3])]
            opps = [OldBotAdapter(unds, [], cap, mod)]
            for nm in names:
                opps.append(StalemateBot() if nm == "stale"
                            else FixedWidthBot(f"Fixed Width {arena2.WIDTH[nm]}", mp, arena2.WIDTH[nm]))
            _, pnl = run_session(mp, CAL, opps, cap, seed=60000 + s)
            ours = pnl.get("Hamza Khan", 0.0)
            theirs = pnl.get("MM-prev (v9)", 0.0)
            rivals = [k for k in pnl if k != "Hamza Khan"]
            s_mm2.append(0.4 + 0.6 * sum(1 for k in rivals if ours > pnl[k]) / len(rivals))
            rivals_p = [k for k in pnl if k != "MM-prev (v9)"]
            s_prev.append(0.4 + 0.6 * sum(1 for k in rivals_p if theirs > pnl[k]) / len(rivals_p))
            p_mm2.append(ours)
            p_prev.append(theirs)
        mm2_scores.append(statistics.fmean(s_mm2))
        prev_scores.append(statistics.fmean(s_prev))
        print(f"{tc:>6}{cap:>5.0f}{'+'.join(names):>22}{statistics.fmean(s_mm2):>11.3f}"
              f"{statistics.fmean(s_prev):>12.3f}{statistics.fmean(p_mm2):>+10.2f}"
              f"{statistics.fmean(p_prev):>+10.2f}")

    m, p = statistics.fmean(mm2_scores), statistics.fmean(prev_scores)
    print(f"\n{'MEAN RANK SCORE':>33}{m:>11.3f}{p:>12.3f}")
    print(f"{'implied 16-test total':>33}{m * 16 + 4:>11.1f}{p * 16 + 4:>12.1f}")
    print(f"\nlive grader reference: mm2 17.4, prev-gen 14.6")
    verdict = ("CONSISTENT with live: mm2 ahead" if m > p else
               "CONTRADICTS live: prev ahead on rank too -- investigate")
    print(f"verdict: {verdict}")


if __name__ == "__main__":
    main()
