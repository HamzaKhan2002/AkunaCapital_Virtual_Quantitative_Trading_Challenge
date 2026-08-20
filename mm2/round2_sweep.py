"""
ONE bot must serve both rounds -- no code change between them.

So the question is not "which is better for round 2" but whether a round-2 gain
covers a MEASURED round-1 loss. mm3 cost exactly -0.2 live (TC13 1.0 -> 0.8).
Anything that changes fill sizes will disturb TC13's $0.11 cushion the same way,
so treat -0.2 as the entry price for any deployment change.

Train/test split is on OPPONENT TYPE, not on seeds -- that is the split that
matters for an unseen field:
    TRAIN    Sniper 1c            (disciplined, margin-aware)
    TEST     Aggressor 2c         (no margin discipline)
             Adaptive             (reactive width)
             mixed 2- and 3-bot rosters

Reported per variant: our PnL, our rank score, and bankruptcies. Ruin is
disqualifying regardless of PnL -- it scores 0, below the 0.4 floor.
"""
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arena2  # noqa: E402
from arena2 import FlowConfig, draw_params, run_session  # noqa: E402
from audit_adversary import Adaptive, Aggressor, Sniper  # noqa: E402
import Market_Maker_2 as MM  # noqa: E402

CAL = FlowConfig("neutral", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)
N = 40
CAPS = (10.0, 20.0, 40.0)

VARIANTS = {
    "mm2  .40/.25 (shipped)": ({"UNINF": .40, "UNKNOWN": .25, "INFORMED": .02}, .60),
    "     .50/.35":           ({"UNINF": .50, "UNKNOWN": .35, "INFORMED": .02}, .65),
    "mm3  .65/.45":           ({"UNINF": .65, "UNKNOWN": .45, "INFORMED": .02}, .75),
    "     .80/.60":           ({"UNINF": .80, "UNKNOWN": .60, "INFORMED": .02}, .85),
    "     .90/.75":           ({"UNINF": .90, "UNKNOWN": .75, "INFORMED": .02}, .90),
}

FIELDS = {
    "TRAIN Sniper":        lambda mp, c: [Sniper(mp, c)],
    "TEST  Aggressor":     lambda mp, c: [Aggressor(mp, c)],
    "TEST  Adaptive":      lambda mp, c: [Adaptive(mp, c)],
    "TEST  Sniper+Aggr":   lambda mp, c: [Sniper(mp, c), Aggressor(mp, c)],
    "TEST  3-bot mixed":   lambda mp, c: [Sniper(mp, c), Aggressor(mp, c),
                                          Adaptive(mp, c)],
}


def measure(field_fn):
    sc, pn, ruin = [], [], 0
    for cap in CAPS:
        for s in range(N):
            rng = random.Random(910_000 + s)
            mp = draw_params(rng)
            score, pnl = run_session(mp, CAL, field_fn(mp, cap), cap, 910_000 + s)
            sc.append(score)
            pn.append(pnl.get("Hamza Khan", 0.0))
            if score == 0.0:
                ruin += 1
    return statistics.fmean(sc), statistics.fmean(pn), ruin


def main() -> int:
    arena2.MarketMaker = MM.MarketMaker
    base_q, base_m = MM.MarketMaker.QUOTE_LOCK_FRAC, MM.MarketMaker.MAX_LOCKED_FRAC
    results = {}
    for label, (q, m) in VARIANTS.items():
        MM.MarketMaker.QUOTE_LOCK_FRAC = q
        MM.MarketMaker.MAX_LOCKED_FRAC = m
        results[label] = {f: measure(fn) for f, fn in FIELDS.items()}
    MM.MarketMaker.QUOTE_LOCK_FRAC, MM.MarketMaker.MAX_LOCKED_FRAC = base_q, base_m

    for metric, idx, fmt in (("RANK SCORE", 0, "{:>9.3f}"),
                             ("OUR PnL", 1, "{:>+9.2f}"),
                             ("BANKRUPTCIES", 2, "{:>9d}")):
        print(f"\n{'=' * 78}\n{metric}  ({N} seeds x {len(CAPS)} capitals per cell)\n{'=' * 78}")
        print(f"{'variant':<24}" + "".join(f"{f:>15}" for f in FIELDS))
        for label in VARIANTS:
            row = "".join(fmt.format(results[label][f][idx]).rjust(15) for f in FIELDS)
            print(f"{label:<24}{row}")

    print(f"\n{'=' * 78}\nDECISION: round-2 gain vs the KNOWN -0.20 round-1 cost\n{'=' * 78}")
    base = results["mm2  .40/.25 (shipped)"]
    test_fields = [f for f in FIELDS if f.startswith("TEST")]
    print(f"{'variant':<24}{'mean TEST score':>17}{'vs mm2':>10}"
          f"{'x16 tests':>11}{'net of -0.20':>14}")
    for label in VARIANTS:
        m = statistics.fmean(results[label][f][0] for f in test_fields)
        b = statistics.fmean(base[f][0] for f in test_fields)
        d = m - b
        print(f"{label:<24}{m:>17.3f}{d:>+10.3f}{d * 16:>+11.2f}"
              f"{d * 16 - 0.20:>+14.2f}")
    print("\n'x16 tests' assumes round 2 is scored like round 1 (16 sessions).")
    print("'net' subtracts the measured round-1 cost of perturbing TC13.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
