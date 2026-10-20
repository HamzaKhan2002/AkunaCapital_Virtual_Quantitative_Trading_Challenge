"""Why does prev-gen dominate the arena's RFQ channel yet score 14.6 vs mm2's 17.4 live?

Hypothesis: the arena hands FixedWidth opponents the TRUE model, so they price
perfectly while we estimate. Every auction we win against a perfectly-informed
rival is a winner's-curse loss => ALL flow is net-adverse => whichever bot trades
LESS wins. prev-gen's lambda-book is far wider than mm2's, so it trades less.
That is the same degenerate pattern that produced "CAPITAL_WIDEN=1.2 is best".

Test: give the opponents an ESTIMATED theo from the same warm-up history (a fair
model of a competent competitor bot, and of Round-2 rivals). If the ranking flips
or collapses, the arena's perfect-information opponents were the calibration bug.
"""
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arena2  # noqa: E402
from arena2 import FlowConfig, StalemateBot, draw_params, penny, run_session, true_model  # noqa: E402
from head_to_head import OldBotAdapter, load_old_bot  # noqa: E402
from Market_Maker_2 import MarketMaker, Underlying as U2, _price  # noqa: E402


class EstimatingWidthBot:
    """Fixed-width quoter that ESTIMATES the model from the warm-up, like a real
    competitor would, instead of being handed the generator's true parameters."""

    def __init__(self, name, width, size=60):
        self.name, self.w, self.size = name, width, size
        self._est = MarketMaker([U2("FED", 1, 2.0), U2("AJR", 2, 1.0), U2("THR", 3, 1.0)], [], 1e9)
        self._vals = {}

    def warm_up(self, hist):
        self._est.warm_up(hist)

    def on_step_advance(self, unds, opts):
        self._vals = {u.underlying_id: u.value for u in unds}

    def on_trade(self, *a):
        pass

    def theo(self, option):
        return _price(self._est._the_model(), option, self._vals)

    def quote(self, option, cp):
        t = self.theo(option)
        b, o = penny(t - self.w / 2.0), penny(t + self.w / 2.0)
        if b >= o:
            b = penny(max(o - 0.01, 0.0))
        return b, self.size, o, self.size

    def respond_to_fok(self, option, fok):
        t = self.theo(option)
        edge = (fok.price - t) if fok.order_type is arena2.OrderType.BUY else (t - fok.price)
        return edge >= self.w / 2.0


def duel(mod, cfg, n, opp_builder, label):
    we = they = 0
    ours_l, theirs_l = [], []
    for s in range(n):
        rng = random.Random(70000 + s)
        mp = draw_params(rng)
        rng2 = random.Random(70000 + s)
        _ = draw_params(rng2)
        v = {1: max(round(rng2.uniform(0.5, 5.0) * 4) / 4, 0.0),
             2: round(rng2.uniform(400, 1500), 2), 3: round(rng2.uniform(400, 1500), 2)}
        unds = [U2("FED", 1, v[1]), U2("AJR", 2, v[2]), U2("THR", 3, v[3])]
        opps = [OldBotAdapter(unds, [], 20.0, mod)] + opp_builder(mp)
        _, pnl = run_session(mp, cfg, opps, 20.0, seed=70000 + s)
        o, t = pnl.get("Hamza Khan", 0.0), pnl.get("MM-prev (v9)", 0.0)
        ours_l.append(o)
        theirs_l.append(t)
        we += o > t + 1e-9
        they += t > o + 1e-9
    print(f"  {label:>42}: mm2 {we:>2}/{n}  prev {they:>2} | "
          f"mm2 {statistics.fmean(ours_l):+8.2f}  prev {statistics.fmean(theirs_l):+8.2f}")


def main():
    mod = load_old_bot()
    n = 60
    cfg = FlowConfig("neutral", 4, 2, 12)

    print("A) opponents given the TRUE model (the arena as originally built):")
    duel(mod, cfg, n,
         lambda mp: [arena2.FixedWidthBot("Fixed Width 0.1", mp, 0.10), StalemateBot()],
         "true-theo FW0.1 + Stalemate")

    print("\nB) opponents ESTIMATE from the same warm-up (realistic competitor):")
    duel(mod, cfg, n,
         lambda mp: [EstimatingWidthBot("Fixed Width 0.1", 0.10), StalemateBot()],
         "estimating FW0.1 + Stalemate")

    print("\nC) estimating opponents, no Stalemate (pure MM-vs-MM competition):")
    duel(mod, cfg, n,
         lambda mp: [EstimatingWidthBot("Fixed Width 0.05", 0.05),
                     EstimatingWidthBot("Fixed Width 0.1", 0.10)],
         "estimating FW0.05 + FW0.1")

    print("\nIf mm2's standing improves markedly from A to B/C, the arena's")
    print("perfect-information opponents were making ALL trading -EV, which is the")
    print("same bug that produced the CAPITAL_WIDEN=1.2 recommendation.")


if __name__ == "__main__":
    main()
