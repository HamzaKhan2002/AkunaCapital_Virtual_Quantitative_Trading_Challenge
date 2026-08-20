"""
Is 17.4 a local maximum, or are we just not trying hard enough?

This is answerable from measured live data alone -- no arena, no model.

A rank score changes ONLY when a PnL ordering flips. So for a perturbation of
magnitude d (in dollars of session PnL), the set of tests that can change state
is exactly those whose margin is smaller than d:

    a test we LOSE  flips to a gain if  d > gap      (points reachable)
    a test we WIN   flips to a loss if  d > cushion  (points exposed)

If, for every d, exposed >= reachable, then no perturbation of any size has
positive expected value and 17.4 is a local maximum in the strong sense --
not "we ran out of ideas" but "the geometry forbids improvement".

Margins are read from the Run 12 grader log.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_diff import BASE_POINTS, SCORED_FROM, margins, parse  # noqa: E402

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "Compiler_Messages_Run_12.txt")


def main() -> int:
    runs = parse(LOG)
    reach, expose = [], []
    for tc, r in sorted(runs.items()):
        if tc < SCORED_FROM:
            continue
        need, cushion, beaten, n = margins(r)
        step = 0.6 / n                      # one rank flip, this test
        if need is not None:
            reach.append((need, step, tc))
        if cushion is not None:
            expose.append((cushion, step, tc))

    events = sorted({d for d, _, _ in reach} | {d for d, _, _ in expose})
    print("d = size of a PnL perturbation, in dollars per session")
    print(f"\n{'d':>8}{'reachable':>11}{'exposed':>10}{'net':>9}   what enters at this d")
    best = (None, -9e9)
    for d in events:
        g = sum(s for m, s, _ in reach if m <= d)
        l = sum(s for m, s, _ in expose if m <= d)
        entering = ([f"+TC{t}" for m, _, t in reach if m == d]
                    + [f"-TC{t}" for m, _, t in expose if m == d])
        net = g - l
        if net > best[1]:
            best = (d, net)
        print(f"{d:>8.2f}{g:>11.2f}{l:>10.2f}{net:>+9.2f}   {' '.join(entering)}")

    print(f"\ncurrent total: {BASE_POINTS + sum(r['score'] for tc, r in runs.items() if tc >= SCORED_FROM):.1f}")
    d, net = best
    print(f"best achievable net over all perturbation sizes: {net:+.2f} (at d = ${d:.2f})")
    if net <= 0:
        print("\n=> For EVERY perturbation size, exposed >= reachable.")
        print("   17.4 is a local maximum by the geometry of the margins, not by")
        print("   exhaustion of ideas. Any blind change is -EV; only a change that")
        print("   is PROVABLY inert on the small-cushion tests can be worth trying.")
    else:
        print(f"\n=> A perturbation of ~${d:.2f} is net positive ({net:+.2f}). Not a local max.")

    print("\nthe binding constraint, sorted:")
    for m, s, tc in sorted(expose)[:5]:
        print(f"   lose TC{tc:<3} if we move more than ${m:>6.2f}  ({-s:+.2f})")
    for m, s, tc in sorted(reach)[:3]:
        print(f"   gain TC{tc:<3} if we move more than ${m:>6.2f}  ({s:+.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
