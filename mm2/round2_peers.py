"""
Round-2 head-to-head: mm6 versus a field of STRONG bots, at the capital and flow
levels the community simulator treats as plausible.

Round 2 is described as "the strongest bots against each other" with no code
change. So the question is not "does mm6 beat Stalemate" -- it is "does mm6 beat
peers who also price correctly, also manage margin, and also work the extremes".

Peers (all given the TRUE model, i.e. no estimation error -- harder than real):
  Peer-tight   3c width, budget-sized, disciplined
  Peer-ladder  3c width PLUS an extreme-price ladder (our own trick, ungated)
  Peer-fat     3c width, 2x our capital deployment
  Sniper 1c / Adaptive  from audit_adversary

Reported as rank score: 0.4 = last, 1.0 = beat everyone.
"""
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arena2  # noqa: E402
from arena2 import FlowConfig, draw_params, penny, run_session, true_model  # noqa: E402
from audit_adversary import Adaptive, Sniper  # noqa: E402
import Market_Maker_2 as MM2  # noqa: E402
import Market_Maker_6 as MM6  # noqa: E402
from Market_Maker_2 import OrderType, _price  # noqa: E402

for _m in (MM6,):
    _m.OrderType = MM2.OrderType
    _m.FokOrder = MM2.FokOrder
    _m.BinaryOption = MM2.BinaryOption
    _m.Underlying = MM2.Underlying
    _m.MarketHistory = MM2.MarketHistory

N = 50


class Peer:
    """Competent peer: exact theo, 3c width, budget sizing, optional ladder."""

    def __init__(self, mp, cap, name, ladder=False, frac=0.25):
        self.name, self._m, self.free = name, true_model(mp), cap
        self.ladder, self.frac, self._vals = ladder, frac, {}

    def warm_up(self, h): pass

    def on_step_advance(self, u, o):
        self._vals = {x.underlying_id: x.value for x in u}

    def on_trade(self, option, price, qty, cp):
        self.free -= qty * price if qty >= 0 else (-qty) * (1.0 - price)

    def theo(self, o):
        return _price(self._m, o, self._vals)

    def quote(self, option, cp):
        t = self.theo(option)
        b, o = penny(t - 0.015), penny(t + 0.015)
        if self.ladder:
            b, o = min(b, 0.05), max(o, 0.95)
        b = max(0.0, min(b, 0.99))
        o = min(1.0, max(o, b + 0.01))
        bud = self.frac * max(self.free, 0.0)
        return (b, max(1, int(bud / max(b, .01))), o,
                max(1, int(bud / max(1 - o, .01))))

    def respond_to_fok(self, option, fok):
        t = self.theo(option)
        e = (fok.price - t) if fok.order_type is OrderType.BUY else (t - fok.price)
        return e >= 0.015


FIELDS = {
    "3 peers (tight)": lambda mp, c: [Peer(mp, c, "P1"), Peer(mp, c, "P2"),
                                      Peer(mp, c, "P3")],
    "2 peers + ladder": lambda mp, c: [Peer(mp, c, "P1"),
                                       Peer(mp, c, "P2-lad", ladder=True)],
    "peer-ladder x2": lambda mp, c: [Peer(mp, c, "P1-lad", ladder=True),
                                     Peer(mp, c, "P2-lad", ladder=True)],
    "peer-fat (2x cap)": lambda mp, c: [Peer(mp, c, "P-fat", frac=0.50),
                                        Peer(mp, c, "P2")],
    "sniper + adaptive": lambda mp, c: [Sniper(mp, c), Adaptive(mp, c)],
    "all-star": lambda mp, c: [Peer(mp, c, "P-lad", ladder=True),
                               Peer(mp, c, "P-fat", frac=0.50), Sniper(mp, c)],
}


def main() -> int:
    flow = FlowConfig("neutral", 4, 2, 12, big_order_prob=0.12, big_qty_hi=100)
    print("rank score vs STRONG peers, community-simulator flow (4 RFQ + 2 FOK/day)\n")
    print(f"{'field':<20}" + "".join(f"{'$' + str(c):>10}" for c in (10, 20, 40, 60))
          + f"{'mean':>9}")
    grand = []
    for label, fn in FIELDS.items():
        row = []
        for cap in (10.0, 20.0, 40.0, 60.0):
            sc = []
            for s in range(N):
                arena2.MarketMaker = MM6.MarketMaker
                rng = random.Random(970_000 + s)
                mp = draw_params(rng)
                score, _ = run_session(mp, flow, fn(mp, cap), cap, 970_000 + s)
                sc.append(score)
            row.append(statistics.fmean(sc))
        grand.extend(row)
        print(f"{label:<20}" + "".join(f"{v:>10.3f}" for v in row)
              + f"{statistics.fmean(row):>9.3f}")
    print(f"\n{'OVERALL':<20}{'':>40}{statistics.fmean(grand):>9.3f}")
    print("\n  0.400 = last in every session, 1.000 = beat every peer every time.")
    print("  Peers here have ZERO estimation error; we estimate from warm-up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
