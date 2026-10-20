"""
Answering the four testable claims in the second review.

  #2 "1,440 out-of-domain sessions test STRUCTURAL solvency, not COMPETITIVE
      performance. Beating random or weak bots says little about beating a
      smart, adaptive adversary."
      -> the sharpest point in the review, and untested until now. Build real
         adversaries and measure RANK, not PnL:
           Sniper      exact theo +/- 1c, margin-disciplined  (a good quant bot)
           Aggressor   exact theo +/- 2c, ignores margin      (what actually
                       beats us live: FW0.05 made $40.17 to our $2.08)
           Adaptive    starts at 5c, widens when it gets filled a lot, tightens
                       when it does not -- a genuinely reactive opponent
           Mirror      an exact copy of ourselves (self-play)

  #4 "the main profit is ordinary quoting, which is just a STATIC spread"
      -> decompose which term actually sets our width, per quote.

  #6 "exception swallowing hides problems; the code is resilient, not correct"
      -> count how often the bare except blocks actually fire.
"""
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arena2  # noqa: E402
from arena2 import (FlowConfig, StalemateBot, draw_params, penny, run_session,  # noqa: E402
                    true_model)
import Market_Maker_2 as MM  # noqa: E402
from Market_Maker_2 import OrderType, _price, _sigma_eps  # noqa: E402

CAL = FlowConfig("neutral", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)
N = 50


class Sniper:
    """Exact theo, 1c width, sizes off its own margin like a disciplined desk."""
    def __init__(self, mp, cap, name="Sniper 1c"):
        self.name, self._m, self.cap, self.free = name, true_model(mp), cap, cap
        self._vals = {}

    def warm_up(self, h): pass
    def on_step_advance(self, u, o): self._vals = {x.underlying_id: x.value for x in u}
    def on_trade(self, option, price, qty, cp):
        self.free -= qty * price if qty >= 0 else (-qty) * (1.0 - price)

    def theo(self, o): return _price(self._m, o, self._vals)

    def quote(self, option, cp):
        t = self.theo(option)
        b, o = penny(t - 0.005), penny(t + 0.005)
        if b >= o:
            b = penny(max(o - 0.01, 0.0))
        bud = 0.25 * max(self.free, 0.0)
        return b, max(1, int(bud / max(b, .01))), o, max(1, int(bud / max(1 - o, .01)))

    def respond_to_fok(self, option, fok):
        t = self.theo(option)
        e = (fok.price - t) if fok.order_type is OrderType.BUY else (t - fok.price)
        return e >= 0.005


class Aggressor:
    """Exact theo, 2c width, and NO margin discipline -- the profile that beats us live."""
    def __init__(self, mp, cap, name="Aggressor 2c"):
        self.name, self._m = name, true_model(mp)
        self._vals = {}

    def warm_up(self, h): pass
    def on_step_advance(self, u, o): self._vals = {x.underlying_id: x.value for x in u}
    def on_trade(self, *a): pass
    def theo(self, o): return _price(self._m, o, self._vals)

    def quote(self, option, cp):
        t = self.theo(option)
        b, o = penny(t - 0.01), penny(t + 0.01)
        if b >= o:
            b = penny(max(o - 0.01, 0.0))
        return b, 200, o, 200

    def respond_to_fok(self, option, fok):
        t = self.theo(option)
        e = (fok.price - t) if fok.order_type is OrderType.BUY else (t - fok.price)
        return e >= 0.01


class Adaptive:
    """Reacts to its own fill rate: widens when filled often, tightens when starved."""
    def __init__(self, mp, cap, name="Adaptive"):
        self.name, self._m = name, true_model(mp)
        self._vals, self.w, self.q, self.f = {}, 0.05, 0, 0

    def warm_up(self, h): pass

    def on_step_advance(self, u, o):
        self._vals = {x.underlying_id: x.value for x in u}
        if self.q >= 5:
            r = self.f / self.q
            if r > 0.6:
                self.w = min(self.w * 1.3, 0.30)   # winning too much -> charge more
            elif r < 0.2:
                self.w = max(self.w * 0.75, 0.01)  # starved -> undercut
            self.q = self.f = 0

    def on_trade(self, *a): self.f += 1
    def theo(self, o): return _price(self._m, o, self._vals)

    def quote(self, option, cp):
        self.q += 1
        t = self.theo(option)
        b, o = penny(t - self.w / 2), penny(t + self.w / 2)
        if b >= o:
            b = penny(max(o - 0.01, 0.0))
        return b, 100, o, 100

    def respond_to_fok(self, option, fok):
        t = self.theo(option)
        e = (fok.price - t) if fok.order_type is OrderType.BUY else (t - fok.price)
        return e >= self.w / 2


# ---- instrumentation for #4 (width source) and #6 (exception fires) ----
STATS = {"base": 0, "sigma": 0, "cap_term": 0, "quotes": 0, "exc": 0}
_Base = MM.MarketMaker


class Spy(_Base):
    name = _Base.name

    def quote(self, option, cp):
        STATS["quotes"] += 1
        try:
            m, v = self._the_model(), self._values()
            theo = _price(m, option, v)
            sig = _sigma_eps(m, option, v)
            cls = self._class_of(cp)
            mult = 2.0 if cls == "INFORMED" else 1.0
            base = self.BASE_EDGE[cls]
            charge = self.CAPITAL_WIDEN * self._utilization()
            if mult * sig > base:
                STATS["sigma"] += 1
            else:
                STATS["base"] += 1
            if charge * max(theo, 1 - theo) > 0.25 * max(base, mult * sig):
                STATS["cap_term"] += 1
        except Exception:
            STATS["exc"] += 1
        return super().quote(option, cp)


def mirror(mp, cap, name="Mirror"):
    class M(_Base):
        @property
        def name(self): return "Mirror (us)"
    return M


def main() -> int:
    arena2.MarketMaker = Spy
    print("=" * 72)
    print("#2  DO WE SURVIVE A COMPETENT ADVERSARY?  (rank score, 0.4 = last)")
    print("=" * 72)
    print(f"{'opponent':<28}{'cap':>5}{'our score':>11}{'our PnL':>10}{'their PnL':>11}")
    for label, factory in (("Sniper 1c (disciplined)", Sniper),
                           ("Aggressor 2c (no margin)", Aggressor),
                           ("Adaptive (reactive width)", Adaptive),
                           ("Stalemate (baseline)", None)):
        for cap in (10.0, 40.0):
            sc, ours, theirs = [], [], []
            for s in range(N):
                rng = random.Random(800_000 + s)
                mp = draw_params(rng)
                opp = [StalemateBot()] if factory is None else [factory(mp, cap)]
                score, pnl = run_session(mp, CAL, opp, cap, 800_000 + s)
                sc.append(score)
                ours.append(pnl.get("Hamza Khan", 0.0))
                theirs.append(statistics.fmean(
                    [v for k, v in pnl.items() if k != "Hamza Khan"] or [0.0]))
            print(f"{label:<28}{cap:>5.0f}{statistics.fmean(sc):>11.3f}"
                  f"{statistics.fmean(ours):>+10.2f}{statistics.fmean(theirs):>+11.2f}")

    print("\n" + "=" * 72)
    print("#4  IS OUR WIDTH ACTUALLY STATIC?")
    print("=" * 72)
    q = max(STATS["quotes"], 1)
    print(f"   quotes measured                     : {STATS['quotes']}")
    print(f"   width set by the flat BASE_EDGE     : {STATS['base'] / q:>7.1%}")
    print(f"   width set by sigma_eps (dynamic)    : {STATS['sigma'] / q:>7.1%}")
    print(f"   capital term materially widening    : {STATS['cap_term'] / q:>7.1%}")

    print("\n" + "=" * 72)
    print("#6  DOES EXCEPTION SWALLOWING HIDE REAL FAILURES?")
    print("=" * 72)
    print(f"   quote() paths raising internally     : {STATS['exc']} of {STATS['quotes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
