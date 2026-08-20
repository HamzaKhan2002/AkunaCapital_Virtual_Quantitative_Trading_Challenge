"""Paired A/B harness on the reverse-engineered arena.

The arena's ABSOLUTE scores are biased (mm2/arena2.py validation: mean |err| ~0.10
vs real grader outcomes), so it cannot predict a score. But for a PAIRED test --
identical seed, identical parameters, identical flow, identical opponents, only
our own config differing -- that bias is common to both arms and cancels. This
gives the statistical power that 1 grader submission (1 noisy bit) never could.

Reports the mean paired difference with a normal-approximation 95% CI, plus the
win/loss/tie split across sessions.
"""
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arena2 import KNOWN_TESTS, FLOWS, build, draw_params, run_session  # noqa: E402
from Market_Maker_2 import MarketMaker  # noqa: E402


def run_arm(setter, n, flow_name="neutral"):
    """Returns per-(test, seed) scores under a given config, in a fixed order."""
    saved = {k: getattr(MarketMaker, k) for k in dir(MarketMaker) if k.isupper()}
    setter()
    try:
        out = []
        for tc, (cap, names, _actual) in KNOWN_TESTS.items():
            for s in range(n):
                rng = random.Random(90000 + s)
                mp = draw_params(rng)
                sc, pnl = run_session(mp, FLOWS[flow_name], build(names, mp), cap, seed=90000 + s)
                out.append((tc, s, sc, pnl["Hamza Khan"]))
        return out
    finally:
        for k, v in saved.items():
            setattr(MarketMaker, k, v)


def ab(label_a, setter_a, label_b, setter_b, n=80, flow_name="neutral"):
    a = run_arm(setter_a, n, flow_name)
    b = run_arm(setter_b, n, flow_name)
    assert [(t, s) for t, s, _, _ in a] == [(t, s) for t, s, _, _ in b]

    diffs = [bb[2] - aa[2] for aa, bb in zip(a, b)]
    pnl_diffs = [bb[3] - aa[3] for aa, bb in zip(a, b)]
    n_tot = len(diffs)
    mean = statistics.fmean(diffs)
    sd = statistics.pstdev(diffs)
    se = sd / (n_tot ** 0.5) if n_tot else 0.0
    lo, hi = mean - 1.96 * se, mean + 1.96 * se
    wins = sum(1 for d in diffs if d > 1e-9)
    losses = sum(1 for d in diffs if d < -1e-9)

    print(f"\n=== {label_b}  vs  {label_a} ===")
    print(f"  paired sessions      : {n_tot}  ({len(KNOWN_TESTS)} tests x {n} seeds)")
    print(f"  mean score delta     : {mean:+.4f}   95% CI [{lo:+.4f}, {hi:+.4f}]")
    print(f"  mean our-PnL delta   : {statistics.fmean(pnl_diffs):+.3f}")
    print(f"  sessions better/worse: {wins} / {losses}  (tied {n_tot - wins - losses})")
    verdict = ("SIGNIFICANT GAIN" if lo > 0 else
               "SIGNIFICANT LOSS" if hi < 0 else "NOT SIGNIFICANT (CI spans 0)")
    print(f"  verdict              : {verdict}")

    per_test = {}
    for aa, bb in zip(a, b):
        per_test.setdefault(aa[0], []).append(bb[2] - aa[2])
    print("  per-test delta       : " + "  ".join(
        f"{t}:{statistics.fmean(v):+.2f}" for t, v in per_test.items()))
    return mean, lo, hi


def main():
    base = MarketMaker.CAPITAL_WIDEN
    print(f"baseline CAPITAL_WIDEN = {base}")
    print("Testing the one lever never tried live. It is NOT the failed width family:")
    print("it only scales the capacity surcharge and never reduces max(BASE_EDGE, sigma),")
    print("so the winner's-curse floor stays fully intact at every setting.")

    def mk(v):
        def setter():
            MarketMaker.CAPITAL_WIDEN = v
        return setter

    for cand in (0.10, 0.0, 0.40):
        ab(f"CAPITAL_WIDEN={base}", mk(base), f"CAPITAL_WIDEN={cand}", mk(cand), n=80)


if __name__ == "__main__":
    main()
