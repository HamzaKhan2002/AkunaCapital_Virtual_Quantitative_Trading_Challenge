"""Does a REALIZED-PnL drawdown brake risk false-firing in sessions we currently win?

The old v5/v9 architecture had DRAWDOWN_LIMIT_FRAC=0.05 (realized PnL < -5% of
starting cash -> force defensive for the REST of the session) and won TC17
outright (+$25) where the current per-cp mm2 policy loses it (-$19). That old
mechanism is GLOBAL, which is why mm2 replaced it -- but a pure realized-PnL
drawdown brake is a different statistic from the already-REFUTED pooled
settled-z trigger (that one false-fired via sequential z-boundary crossing in
9-15% of benign sessions). This checks the drawdown statistic on its own merits:
for sessions that end up profitable under the CURRENT 17.4 policy, how deep does
realized (settled) PnL ever dip mid-session, as a fraction of starting cash?
"""
import math
import os
import random
import sys
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from map_policy import draw_real  # noqa: E402
import calibrate_sigma as cal  # noqa: E402
from Market_Maker_2 import (  # noqa: E402
    BinaryOption, FokOrder, MarketHistory, MarketMaker, OptionLeg, OrderType, Underlying,
)


def session(seed: int, cash: float, toxic: bool) -> dict:
    rng = random.Random(seed)
    mp = draw_real(rng)
    v = {1: max(round(rng.uniform(0.5, 5.0) * 4) / 4, 0.0),
         2: round(rng.uniform(400, 1500), 2), 3: round(rng.uniform(400, 1500), 2)}
    hist = {k: [x] for k, x in v.items()}
    for _ in range(17):
        v = cal.step(mp, v, rng)
        for k in hist:
            hist[k].append(v[k])
    unds = [Underlying("FED", 1, v[1]), Underlying("AJR", 2, v[2]), Underlying("THR", 3, v[3])]
    oid = [0]

    def mk(steps):
        oid[0] += 1
        k = rng.random()
        if k < 0.35:
            return BinaryOption(legs=(OptionLeg(1, 1.0),), option_id=oid[0], steps_until_expiry=steps,
                                strike=max(round((v[1] + 0.25 * rng.randint(-3, 3)) * 4) / 4, 0.0))
        if k < 0.85:
            u = rng.choice([2, 3])
            return BinaryOption(legs=(OptionLeg(u, 1.0),), option_id=oid[0], steps_until_expiry=steps,
                                strike=round(v[u] * math.exp(rng.gauss(0, 0.06)), 2))
        w = rng.choice([1.0, -1.0])
        return BinaryOption(legs=(OptionLeg(2, w), OptionLeg(3, -w)), option_id=oid[0],
                            steps_until_expiry=steps, strike=0.0)

    active = [mk(rng.randint(1, 5)) for _ in range(5)]
    mm = MarketMaker(unds, list(active), cash)
    mm.warm_up(MarketHistory(values_by_underlying_id={k: tuple(x) for k, x in hist.items()}))

    min_drawdown_frac = 0.0     # most negative (realized cash - initial) / initial seen mid-session
    settled_cash = cash         # realized-only, mirrors the old bot's _realized_pnl + initial
    for _day in range(25):
        for _ in range(rng.randint(1, 4)):
            opt = rng.choice(active)
            cp = rng.randint(100000, 999999)
            q = mm.quote(opt, cp)
            if rng.random() < 0.45:
                if rng.random() < 0.5:
                    mm.on_trade(opt, q.offer_price, -min(rng.randint(1, 10), q.offer_quantity), cp)
                else:
                    mm.on_trade(opt, q.bid_price, min(rng.randint(1, 10), q.bid_quantity), cp)
        for _ in range(rng.randint(0, 2)):
            opt = rng.choice(active)
            cp = rng.randint(100000, 999999)
            th = mm.price_option(opt)
            px = th + (rng.uniform(-0.05, 0.02) if toxic else rng.uniform(-0.2, 0.4))
            f = FokOrder(counterparty_id=cp, option_id=opt.option_id,
                         order_type=rng.choice([OrderType.BUY, OrderType.SELL]),
                         price=min(max(round(px, 2), 0.01), 0.99), quantity=rng.randint(1, 60))
            if mm.respond_to_fok(opt, f):
                mm.on_trade(opt, f.price, -f.quantity if f.order_type is OrderType.BUY else f.quantity, cp)
        v[1] = max(round(v[1] + rng.choice([-0.25, 0.0, 0.25]), 2), 0.0)
        v[2] = round(v[2] * math.exp(rng.gauss(0, 0.02)), 2)
        v[3] = round(v[3] * math.exp(rng.gauss(0, 0.03)), 2)
        nxt = [o.advance_step() for o in active]
        nxt = [o for o in nxt if o.steps_until_expiry > 0]
        while len(nxt) < 5:
            nxt.append(mk(rng.randint(1, 5)))
        settled_before = mm._free + mm._locked
        mm.on_step_advance([Underlying("FED", 1, v[1]), Underlying("AJR", 2, v[2]),
                            Underlying("THR", 3, v[3])], nxt)
        active = [o for o in nxt if o.steps_until_expiry > 0]
        # Realized-only PnL: settled cash the OLD bot would have tracked (excludes
        # unsettled locks, which are neither wins nor losses yet).
        realized_cash = cash - sum(q * p if q >= 0 else (-q) * (1.0 - p)
                                   for trades in mm._locks.values() for q, p, _ in trades)
        realized_cash += (mm._free + mm._locked) - settled_before - (
            (mm._free + mm._locked) - settled_before)  # placeholder, corrected below
        # Simpler and exact: total wealth (free+locked) IS realized settled PnL plus
        # still-open locks valued at their trade price (a fair proxy for "realized so far").
        wealth = mm._free + mm._locked
        min_drawdown_frac = min(min_drawdown_frac, (wealth - cash) / cash)

    final_wealth = mm._free + mm._locked
    return {"final_pnl_frac": (final_wealth - cash) / cash, "min_drawdown_frac": min_drawdown_frac}


def main() -> None:
    for label, toxic in (("BENIGN", False), ("TOXIC", True)):
        stats = [session(20000 + s, [10.0, 20.0, 40.0][s % 3], toxic) for s in range(300)]
        profitable = [s for s in stats if s["final_pnl_frac"] > 0]
        print(f"{label}: n={len(stats)}  profitable={len(profitable)}")
        for thresh in (0.10, 0.15, 0.20, 0.25, 0.30):
            fires_among_profitable = sum(1 for s in profitable if s["min_drawdown_frac"] <= -thresh)
            print(f"    drawdown brake at -{thresh:.0%}: fires in {fires_among_profitable}/{len(profitable)} "
                  f"({fires_among_profitable / max(len(profitable), 1):.1%}) of sessions that end PROFITABLE")
        worst = min(s["min_drawdown_frac"] for s in stats)
        print(f"    worst drawdown seen overall: {worst:.1%}  "
              f"mean final PnL frac: {mean(s['final_pnl_frac'] for s in stats):+.1%}")


if __name__ == "__main__":
    main()
