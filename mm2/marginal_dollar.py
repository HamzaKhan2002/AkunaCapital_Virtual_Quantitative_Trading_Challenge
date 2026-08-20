"""
"Margin pays zero" is true -- but the MARGINAL DOLLAR is not worthless. Its value
depends entirely on how close the opponents are.

    score_s = 0.4 + (0.6/n) * SUM_j PHI( (pnl_us - pnl_j) / sigma )

    d score_s / d pnl_us = (0.6/n) * SUM_j phi( gap_j / sigma ) / sigma

phi() is the normal density: it is ~0 when the gap is large and maximal when the
gap is ~0. So a dollar of PnL is worth nothing against distant opponents and a
great deal against close ones.

Round 1 opponents are far away (measured). The competent adversaries built in
audit_adversary.py finish within a few dollars of us (measured). If round 2 is
a field of competent bots, the conversion rate changes by a large factor -- and
PnL maximisation becomes the correct objective even though the scoring rule
never changed.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_diff import SCORED_FROM, parse  # noqa: E402

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "Compiler_Messages_Run_12.txt")
SIGMA = 8.0          # session PnL noise, order of magnitude from stress runs


def dens(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def marginal_value(gaps_by_test, sigma=SIGMA):
    """Expected score gained per +$1 of our PnL, summed over the test suite."""
    tot = 0.0
    per = []
    for tc, gaps in gaps_by_test:
        n = len(gaps)
        if not n:
            continue
        v = 0.6 / n * sum(dens(g / sigma) / sigma for g in gaps)
        per.append((tc, v, min(abs(g) for g in gaps)))
        tot += v
    return tot, per


def main() -> int:
    runs = parse(LOG)
    r1 = []
    for tc, r in sorted(runs.items()):
        if tc < SCORED_FROM:
            continue
        gaps = [r["me"] - v for v in r["others"].values()]
        if gaps:
            r1.append((f"TC{tc}", gaps))

    tot1, per1 = marginal_value(r1)
    print("ROUND 1  (measured, Run 12)")
    print(f"  points gained per +$1 of PnL, whole suite : {tot1:.4f}")
    print(f"  i.e. +$10 of PnL in every test is worth   : {tot1 * 10:+.2f} points")
    print("\n  the three tests where a dollar is worth most:")
    for tc, v, g in sorted(per1, key=lambda x: -x[1])[:3]:
        print(f"     {tc:<6} {v:.4f} pts/$   (nearest opponent ${g:.2f} away)")
    print("  and the three where it is worth least:")
    for tc, v, g in sorted(per1, key=lambda x: x[1])[:3]:
        print(f"     {tc:<6} {v:.4f} pts/$   (nearest opponent ${g:.2f} away)")

    # measured finishes against the competent adversaries (audit_adversary.py)
    r2 = [("Sniper $10", [3.08 - (-0.39)]), ("Sniper $40", [0.50 - (-2.20)]),
          ("Aggressor $10", [2.58 - (-2.10)]), ("Aggressor $40", [-2.34 - (-4.85)]),
          ("Adaptive $10", [2.31 - (-1.34)]), ("Adaptive $40", [-2.27 - (-0.76)])]
    tot2, per2 = marginal_value(r2)
    print(f"\nROUND 2 PROXY  (competent adversaries, measured)")
    print(f"  points gained per +$1 of PnL, per test     : {tot2 / len(r2):.4f}")
    print(f"  round 1 equivalent, per test              : {tot1 / len(r1):.4f}")
    print(f"  => a dollar of PnL is worth "
          f"{(tot2 / len(r2)) / (tot1 / len(r1)):.1f}x MORE against competent bots")

    print("\n  mean |gap| to nearest opponent:")
    print(f"     round 1 rosters      : ${sum(g for _, _, g in per1) / len(per1):>6.2f}")
    print(f"     competent adversaries: ${sum(g for _, _, g in per2) / len(per2):>6.2f}")

    print("\n" + "=" * 70)
    print("WHAT A PURE PnL GAIN WOULD BE WORTH IN ROUND 1 (no variance, no")
    print("trade-off -- a strict Pareto improvement, the one class E61 permits)")
    print("=" * 70)
    base = sum(r["score"] for tc, r in runs.items() if tc >= SCORED_FROM)
    print(f"  {'+$ to our PnL in every test':<30}{'total':>8}{'delta':>8}")
    for bump in (2, 5, 9.24, 14.87, 20.62, 26.35, 38.09):
        tot = 0.0
        for tc, r in sorted(runs.items()):
            if tc < SCORED_FROM:
                continue
            opps = list(r["others"].values())
            if not opps:
                continue
            tot += 0.4 + 0.6 * sum(1 for v in opps if r["me"] + bump > v) / len(opps)
        print(f"  {'+$' + format(bump, '.2f'):<30}{4 + tot:>8.2f}{tot - base:>+8.2f}")
    print("\n  Every step is a genuine gain and NONE costs a test -- because a pure")
    print("  mean increase only widens cushions. This is why 'earn more' and 'run")
    print("  more variance' are not the same proposal: the first is Pareto, the")
    print("  second is a trade-off, and only the second was refuted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
