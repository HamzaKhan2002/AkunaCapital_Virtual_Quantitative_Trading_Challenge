"""
"We don't need to win them all -- win BIG when we win, accept losing elsewhere."

Worth testing properly, because the first-order reading contradicts a measured
fact (margin of victory pays zero: a session won 6.7x scored exactly 1.00) while
the second-order reading is Seel-Strack and may well be right.

The steelman: do not try to win every test. Run MORE VARIANCE. Sessions we lose
are lost by a lot anyway, so extra variance costs little there; sessions we win
have big cushions, so extra variance rarely costs them; and variance converts
some hopeless sessions into wins.

That is a quantitative claim, and every input is measured. For a zero-mean
perturbation X ~ N(0, s^2) added to our session PnL:

    E[score_s] = (1 - P(ruin)) * [ 0.4 + (0.6/n) * SUM_j PHI( (pnl_us - pnl_j)/s ) ]

with P(ruin) ~ PHI(-capital/s), since a loss deeper than the book is bankruptcy
and bankruptcy scores 0. Sweeping s traces the whole risk-appetite frontier.

Also computed: the ORACLE bound -- variance applied only to sessions we are
actually losing. No real policy can beat that, because rank is unobservable
(measured: our own FINAL PnL correlates just +0.434 with rank).
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_diff import BASE_POINTS, SCORED_FROM, parse  # noqa: E402

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "Compiler_Messages_Run_12.txt")


def phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def expected_total(tests, sigma, only_when_losing=False, ruin=True):
    tot = 0.0
    for r in tests:
        us, cap = r["me"], r["capital"] or 10.0
        opps = list(r["others"].values())
        n = len(opps)
        if n == 0:
            tot += 1.0
            continue
        s = sigma
        if only_when_losing and us >= max(opps):
            s = 0.0                      # oracle: no extra risk when already top
        if s <= 1e-9:
            beaten = sum(1 for v in opps if us > v)
            tot += 0.4 + 0.6 * beaten / n
            continue
        p_ruin = phi(-cap / s) if ruin else 0.0
        share = sum(phi((us - v) / s) for v in opps) / n
        tot += (1.0 - p_ruin) * (0.4 + 0.6 * share)
    return BASE_POINTS + tot


def main() -> int:
    runs = parse(LOG)
    tests = [r for tc, r in sorted(runs.items()) if tc >= SCORED_FROM]

    base = expected_total(tests, 0.0)
    print(f"measured baseline (sigma = 0): {base:.2f}\n")
    print(f"{'extra sigma':>12}{'blind':>10}{'oracle':>10}"
          f"{'blind, ruin ignored':>22}")
    best_b = best_o = (0.0, base)
    for s in (0.5, 1, 2, 3, 5, 8, 12, 18, 25, 35, 50, 75, 100):
        b = expected_total(tests, s)
        o = expected_total(tests, s, only_when_losing=True)
        nr = expected_total(tests, s, ruin=False)
        if b > best_b[1]:
            best_b = (s, b)
        if o > best_o[1]:
            best_o = (s, o)
        print(f"{s:>12.1f}{b:>10.2f}{o:>10.2f}{nr:>22.2f}")

    print(f"\nbest BLIND  variance: sigma ${best_b[0]:.1f} -> {best_b[1]:.2f} "
          f"({best_b[1] - base:+.2f})")
    print(f"best ORACLE variance: sigma ${best_o[0]:.1f} -> {best_o[1]:.2f} "
          f"({best_o[1] - base:+.2f})")

    print("\nwhy: per-test sensitivity to a $8 blind variance increase")
    print(f"  {'TC':<6}{'n':>3}{'us':>9}{'best opp':>10}{'now':>7}{'E[score]':>10}{'delta':>8}")
    for tc, r in sorted(runs.items()):
        if tc < SCORED_FROM:
            continue
        us, opps, n = r["me"], list(r["others"].values()), len(r["others"])
        if not n:
            continue
        cap = r["capital"] or 10.0
        cur = 0.4 + 0.6 * sum(1 for v in opps if us > v) / n
        e = (1 - phi(-cap / 8.0)) * (0.4 + 0.6 * sum(phi((us - v) / 8.0) for v in opps) / n)
        print(f"  TC{tc:<4}{n:>3}{us:>9.2f}{max(opps):>10.2f}{cur:>7.2f}"
              f"{e:>10.2f}{e - cur:>+8.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
