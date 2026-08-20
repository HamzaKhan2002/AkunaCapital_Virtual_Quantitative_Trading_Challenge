"""HEAD-TO-HEAD: mm2 (current, 17.4) vs the previous-generation bot (root Market_Maker.py,
v9 lineage) competing IN THE SAME SESSIONS -- the Round-2 format, which grader scores
never measured (each bot only ever faced the fixed archetypes, never each other).

Caveat carried from E53: this arena's flow has no junk-crosser channel, so results
understate extreme-price harvesting for BOTH bots equally; for a relative comparison
between two of our own bots the shared bias is acceptable, and is stated with results.
"""
import importlib.util
import math
import os
import random
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from arena2 import (  # noqa: E402
    FLOWS, FixedWidthBot, StalemateBot, draw_params, run_session,
)
import arena2  # noqa: E402


def load_old_bot():
    """Load the root Market_Maker.py under a private module name."""
    spec = importlib.util.spec_from_file_location("mm_v9", os.path.join(ROOT, "Market_Maker.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mm_v9"] = mod
    spec.loader.exec_module(mod)
    return mod


class OldBotAdapter:
    """Wraps the previous-generation MarketMaker under a distinct name so the
    arena's name-keyed accounts don't collide (both are 'Hamza Khan')."""

    name = "MM-prev (v9)"

    def __init__(self, unds, opts, cash, mod):
        # the old template classes are structurally identical; rebuild inputs with them
        self._m = mod
        u2 = [mod.Underlying(name=u.name, underlying_id=u.underlying_id, value=u.value) for u in unds]
        o2 = [self._conv(o) for o in opts]
        self.bot = mod.MarketMaker(u2, o2, cash)

    def _conv(self, o):
        mod = self._m
        legs = tuple(mod.OptionLeg(underlying_id=leg.underlying_id, weight=leg.weight) for leg in o.legs)
        return mod.BinaryOption(legs=legs, option_id=o.option_id,
                                steps_until_expiry=o.steps_until_expiry, strike=o.strike)

    def warm_up(self, hist):
        self.bot.warm_up(self._m.MarketHistory(values_by_underlying_id=hist.values_by_underlying_id))

    def on_step_advance(self, unds, opts):
        u2 = [self._m.Underlying(name=u.name, underlying_id=u.underlying_id, value=u.value) for u in unds]
        self.bot.on_step_advance(u2, [self._conv(o) for o in opts])

    def on_trade(self, option, price, qty, cp):
        self.bot.on_trade(self._conv(option), price, qty, cp)

    def quote(self, option, cp):
        q = self.bot.quote(self._conv(option), cp)
        return q.bid_price, q.bid_quantity, q.offer_price, q.offer_quantity

    def respond_to_fok(self, option, fok):
        f2 = self._m.FokOrder(counterparty_id=fok.counterparty_id, option_id=fok.option_id,
                              order_type=self._m.OrderType(fok.order_type.value),
                              price=fok.price, quantity=fok.quantity)
        return bool(self.bot.respond_to_fok(self._conv(option), f2))


def main():
    mod = load_old_bot()
    n = 60
    print(f"head-to-head: mm2 vs previous-gen bot in the SAME session, {n} seeds per config")
    print("(shared arena bias: no junk-crosser flow -- affects both bots equally)\n")

    for label, extra in (("duel only (no other MMs)", []),
                         ("with FW0.1 + Stalemate", ["fw10", "stale"]),
                         ("with FW0.05 + FW0.25", ["fw05", "fw25"])):
        for flow_name in ("neutral", "sharp"):
            we_win = they_win = tie = 0
            our_pnls, their_pnls = [], []
            for s in range(n):
                rng = random.Random(70000 + s)
                mp = draw_params(rng)
                opponents = [OldBotAdapter.__new__(OldBotAdapter)]  # placeholder, built in factory
                # build opponents fresh per session
                opps = []
                for nme in extra:
                    opps.append(StalemateBot() if nme == "stale"
                                else FixedWidthBot(f"Fixed Width {arena2.WIDTH[nme]}", mp, arena2.WIDTH[nme]))

                # adapter needs session inputs; hook via a tiny factory closure
                made = {}

                class Factory(OldBotAdapter):
                    def __init__(self2, unds, opts, cash):
                        super().__init__(unds, opts, cash, mod)
                        made["bot"] = self2

                _, pnl = run_session(mp, FLOWS[flow_name], [Factory.__new__(Factory)] if False else
                                     _with_old(mod, opps, mp, rng, s, flow_name),
                                     20.0, seed=70000 + s)
                ours, theirs = pnl.get("Hamza Khan", 0.0), pnl.get("MM-prev (v9)", 0.0)
                our_pnls.append(ours)
                their_pnls.append(theirs)
                if ours > theirs + 1e-9:
                    we_win += 1
                elif theirs > ours + 1e-9:
                    they_win += 1
                else:
                    tie += 1
            print(f"  {label:>28} | {flow_name:>7} flow: mm2 wins {we_win}/{n}, prev wins {they_win}, "
                  f"tie {tie} | mean PnL mm2 {statistics.fmean(our_pnls):+.2f} vs prev "
                  f"{statistics.fmean(their_pnls):+.2f}")


def _with_old(mod, opps, mp, rng, s, flow_name):
    """Return opponents list containing a fresh old-bot adapter factory instance."""
    class _Adapter(OldBotAdapter):
        def __init__(self):
            pass  # real init happens lazily on first warm_up call via arena

    # arena2.run_session builds OUR bot itself and calls opponents' warm_up/on_step_advance
    # with arena-native objects; the adapter needs its own construction. Simplest: construct
    # here with the session's initial state replicated the same way run_session does.
    rng2 = random.Random(70000 + s)
    _ = draw_params(rng2)  # consume identically so the adapter sees the same session RNG stream
    v = {1: max(round(rng2.uniform(0.5, 5.0) * 4) / 4, 0.0),
         2: round(rng2.uniform(400, 1500), 2), 3: round(rng2.uniform(400, 1500), 2)}
    from Market_Maker_2 import Underlying as U2
    unds = [U2("FED", 1, v[1]), U2("AJR", 2, v[2]), U2("THR", 3, v[3])]
    adapter = OldBotAdapter(unds, [], 20.0, mod)
    return [adapter] + opps


if __name__ == "__main__":
    main()
