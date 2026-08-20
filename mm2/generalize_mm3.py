"""
Does mm3 beat mm2 in MORE cases than the 8 known rosters?

The previous harness reported PnL deltas -- the wrong statistic. The grader pays
a RANK score, so a change that leaves our PnL flat while cutting an opponent's
by $16 can still flip a test. This measures the score directly, seed-paired,
across a far wider case set than the visible tests:

  rosters   all 1-3 subsets of {stale, fw02, fw05, fw10, fw25}
  capitals  10 / 20 / 40
  fw02      a 2c-wide bot: proxy for a COMPETENT round-2 opponent, which the
            visible tests do not contain at all (widest visible edge is 5c)

Reported per case: mean rank score for each bot, and the gap-to-flip, so we can
see not just whether mm3 wins but whether it is CLOSE to winning.
"""
import itertools
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arena2  # noqa: E402
from arena2 import FixedWidthBot, FlowConfig, StalemateBot, draw_params, run_session  # noqa: E402
import Market_Maker_2 as MM2  # noqa: E402
import Market_Maker_3 as MM3  # noqa: E402

CAL = FlowConfig("neutral", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)
WIDTH = {"fw02": 0.02, "fw05": 0.05, "fw10": 0.10, "fw25": 0.25}
KINDS = ["stale", "fw02", "fw05", "fw10", "fw25"]
N = 40


def build(names, mp):
    return [StalemateBot() if n == "stale"
            else FixedWidthBot(f"Fixed Width {WIDTH[n]}", mp, WIDTH[n]) for n in names]


def run(module, names, cap, seed):
    arena2.MarketMaker = module.MarketMaker
    rng = random.Random(seed)
    mp = draw_params(rng)
    score, pnl = run_session(mp, CAL, build(names, mp), cap, seed)
    ours = pnl.get("Hamza Khan", 0.0)
    rivals = {k: v for k, v in pnl.items() if k != "Hamza Khan"}
    above = [v for v in rivals.values() if v > ours]
    return score, (min(above) - ours if above else 0.0)


def main() -> int:
    rosters = [c for r in (1, 2, 3) for c in itertools.combinations(KINDS, r)]
    print(f"{len(rosters)} rosters x 3 capitals x {N} seeds, seed-paired\n")
    print(f"{'roster':<24}{'cap':>5}{'mm2':>8}{'mm3':>8}{'delta':>8}"
          f"{'gap mm2':>10}{'gap mm3':>10}")
    tot2 = tot3 = 0.0
    cases = better = worse = close = 0
    rows = []
    for names in rosters:
        for cap in (10.0, 20.0, 40.0):
            s2, s3, g2, g3 = [], [], [], []
            for s in range(N):
                a, ga = run(MM2, names, cap, 300_000 + s)
                b, gb = run(MM3, names, cap, 300_000 + s)
                s2.append(a); s3.append(b); g2.append(ga); g3.append(gb)
            m2, m3 = statistics.fmean(s2), statistics.fmean(s3)
            gm2, gm3 = statistics.fmean(g2), statistics.fmean(g3)
            tot2 += m2; tot3 += m3; cases += 1
            d = m3 - m2
            if d > 0.02:
                better += 1
            elif d < -0.02:
                worse += 1
            if 0 < gm3 < 5.0:
                close += 1
            rows.append((abs(d), "+".join(names), cap, m2, m3, d, gm2, gm3))

    for _, nm, cap, m2, m3, d, gm2, gm3 in sorted(rows, key=lambda r: -r[0])[:18]:
        print(f"{nm:<24}{cap:>5.0f}{m2:>8.3f}{m3:>8.3f}{d:>+8.3f}"
              f"{gm2:>10.2f}{gm3:>10.2f}")

    print(f"\n{'':<24}{'':>5}{'mean':>8}")
    print(f"{'ALL CASES':<24}{'':>5}{tot2 / cases:>8.3f}{tot3 / cases:>8.3f}"
          f"{(tot3 - tot2) / cases:>+8.3f}")
    print(f"\n  cases where mm3 better (>0.02): {better}/{cases}")
    print(f"  cases where mm3 worse  (<-0.02): {worse}/{cases}")
    print(f"  cases mm3 is within $5 of flipping a rank: {close}/{cases}")

    print("\n--- by capital (our live $40 books are TC16-TC20) ---")
    print(f"{'capital':>9}{'mm2':>8}{'mm3':>8}{'delta':>8}{'n':>5}")
    for cap in (10.0, 20.0, 40.0):
        sel = [r for r in rows if r[2] == cap]
        a = statistics.fmean(r[3] for r in sel)
        b = statistics.fmean(r[4] for r in sel)
        print(f"{cap:>9.0f}{a:>8.3f}{b:>8.3f}{b - a:>+8.3f}{len(sel):>5}")

    print("\n--- by whether a 0.00-bidder (Stalemate) is present ---")
    print(f"{'stale?':>9}{'mm2':>8}{'mm3':>8}{'delta':>8}{'n':>5}")
    for flag, lab in ((True, "yes"), (False, "no")):
        sel = [r for r in rows if ("stale" in r[1]) == flag]
        a = statistics.fmean(r[3] for r in sel)
        b = statistics.fmean(r[4] for r in sel)
        print(f"{lab:>9}{a:>8.3f}{b:>8.3f}{b - a:>+8.3f}{len(sel):>5}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
