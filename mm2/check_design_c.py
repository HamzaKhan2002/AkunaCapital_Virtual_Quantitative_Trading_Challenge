"""
Mechanism check for design C. NOT a PnL/ranking test -- the arena is known to
misrank (E53/E55) and is not trusted for that. It is trusted for one thing only:
whether a deterministic trigger fires, which is a property of the quoting rules,
not of the flow calibration.

Pre-registered claim:
    the probe ARMS against a field that bids 0.00, and NEVER arms against any
    fixed-width archetype, because none of them bids below theo - 0.125 while the
    probe sits at 0.45 with theo >= 0.70.

A single arm on a fixed-width-only roster falsifies the change. Zero arms on the
Stalemate rosters would mean the mechanism is dead code.

(v1 of this file read run_session()'s return value, which is (score, pnl) -- so
getattr(float, "_swept") was always False and every roster looked inert,
including the one that must fire. Instances are now captured directly.)
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arena2  # noqa: E402
from arena2 import FLOWS, KNOWN_TESTS, build, draw_params  # noqa: E402

_made: list = []
_Base = arena2.MarketMaker


class _Spy(_Base):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _made.append(self)


arena2.MarketMaker = _Spy


def main() -> int:
    print(f"{'test':<6}{'cap':>5}  {'roster':<20}{'probed':>8}{'armed':>7}"
          f"{'n':>5}   verdict")
    bad = dead = 0
    for tc, (cap, names, _score) in KNOWN_TESTS.items():
        probed = armed = tot = 0
        for seed in range(60):
            rng = random.Random(10_000 + seed)
            mp = draw_params(rng)
            _made.clear()
            arena2.run_session(mp, FLOWS["neutral"], build(names, mp), cap,
                               10_000 + seed)
            if not _made:
                continue
            bot = _made[-1]
            tot += 1
            if bot._probes_left < bot.PROBE_BUDGET:
                probed += 1
            if bot._swept:
                armed += 1

        stale = "stale" in names
        small = cap <= _Base.PROBE_MAX_CAPITAL
        if armed and not stale:
            bad += 1
            verdict = "*** VIOLATION: armed with a fixed-width bot present"
        elif stale and small and armed == 0:
            dead += 1
            verdict = "*** dead: 0.00 bidder present but never armed"
        elif armed:
            verdict = "fires (0.00 bidder present)"
        elif not small:
            verdict = "inert (book above PROBE_MAX_CAPITAL)"
        else:
            verdict = "inert"
        print(f"{tc:<6}{cap:>5.0f}  {str(names):<20}{probed:>8}{armed:>7}"
              f"{tot:>5}   {verdict}")

    print()
    if bad:
        print(f"FAIL: {bad} roster(s) armed when they must not. Do not submit.")
    elif dead:
        print(f"FAIL: {dead} roster(s) should have armed and never did.")
    else:
        print("PASS: fires only where a 0.00 bidder exists; inert everywhere else.")
    return bad + dead


if __name__ == "__main__":
    sys.exit(main())
