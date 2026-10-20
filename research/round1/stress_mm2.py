"""Randomized multi-session stress: solvency, ledger integrity, utilization behaviour."""
import math
import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Market_Maker_2 import (  # noqa: E402
    AJARAI_UNDERLYING_ID, FED_FUNDS_RATE_UNDERLYING_ID, THERIODIC_UNDERLYING_ID,
    BinaryOption, FokOrder, MarketHistory, MarketMaker, OptionLeg, OrderType, Underlying,
)


def run_session(seed: int, cash: float, toxic: bool) -> dict:
    rng = random.Random(seed)
    vals = {FED_FUNDS_RATE_UNDERLYING_ID: 2.0, AJARAI_UNDERLYING_ID: 1000.0,
            THERIODIC_UNDERLYING_ID: 750.0}
    unds = [Underlying("FED", 1, vals[1]), Underlying("AJR", 2, vals[2]), Underlying("THR", 3, vals[3])]
    oid = [0]

    def mk(steps: int) -> BinaryOption:
        oid[0] += 1
        k = rng.random()
        if k < 0.4:
            return BinaryOption(legs=(OptionLeg(1, 1.0),), option_id=oid[0],
                                steps_until_expiry=steps,
                                strike=round(vals[1] + 0.25 * rng.randint(-3, 3), 2))
        if k < 0.85:
            u = rng.choice([2, 3])
            return BinaryOption(legs=(OptionLeg(u, 1.0),), option_id=oid[0],
                                steps_until_expiry=steps,
                                strike=round(vals[u] * math.exp(rng.gauss(0, 0.05)), 2))
        w = rng.choice([1.0, -1.0])
        return BinaryOption(legs=(OptionLeg(2, w), OptionLeg(3, -w)), option_id=oid[0],
                            steps_until_expiry=steps, strike=0.0)

    active = [mk(rng.randint(1, 5)) for _ in range(5)]
    mm = MarketMaker(unds, list(active), cash)
    hist = {1: tuple(max(2.0 + 0.25 * rng.randint(-2, 2), 0.0) for _ in range(18)),
            2: tuple(round(1000 * math.exp(rng.gauss(0, 0.02)), 2) for _ in range(18)),
            3: tuple(round(750 * math.exp(rng.gauss(0, 0.03)), 2) for _ in range(18))}
    mm.warm_up(MarketHistory(values_by_underlying_id=hist))

    min_free, max_util, trades = cash, 0.0, 0
    for _ in range(25):
        for _ in range(rng.randint(1, 5)):
            o = rng.choice(active)
            cp = rng.randint(100000, 999999)          # grader ids are near-unique
            q = mm.quote(o, cp)
            assert 0.0 <= q.bid_price < q.offer_price <= 1.0
            assert q.bid_quantity > 0 and q.offer_quantity > 0
            if rng.random() < 0.45:
                want = rng.randint(1, 10)
                if rng.random() < 0.5:
                    mm.on_trade(o, q.offer_price, -min(want, q.offer_quantity), cp)
                else:
                    mm.on_trade(o, q.bid_price, min(want, q.bid_quantity), cp)
                trades += 1
        for _ in range(rng.randint(0, 3)):
            o = rng.choice(active)
            cp = rng.randint(100000, 999999)
            theo = mm.price_option(o)
            px = theo + (rng.uniform(-0.05, 0.02) if toxic else rng.uniform(-0.2, 0.4))
            px = min(max(round(px, 2), 0.01), 0.99)
            f = FokOrder(counterparty_id=cp, option_id=o.option_id,
                         order_type=rng.choice([OrderType.BUY, OrderType.SELL]),
                         price=px, quantity=rng.randint(1, 60))
            if mm.respond_to_fok(o, f):
                mm.on_trade(o, f.price, -f.quantity if f.order_type is OrderType.BUY else f.quantity, cp)
                trades += 1
        min_free = min(min_free, mm._free)
        max_util = max(max_util, mm._utilization())
        vals[1] = max(round(vals[1] + rng.choice([-0.25, 0.0, 0.25]), 2), 0.0)
        vals[2] = round(vals[2] * math.exp(rng.gauss(0, 0.02)), 2)
        vals[3] = round(vals[3] * math.exp(rng.gauss(0, 0.03)), 2)
        nxt = [o.advance_step() for o in active]
        nxt = [o for o in nxt if o.steps_until_expiry > 0]
        while len(nxt) < 5:
            nxt.append(mk(rng.randint(1, 5)))
        unds2 = [Underlying("FED", 1, vals[1]), Underlying("AJR", 2, vals[2]), Underlying("THR", 3, vals[3])]
        mm.on_step_advance(unds2, nxt)
        active = [o for o in nxt if o.steps_until_expiry > 0]

    # drain: expire everything still open, then the lock ledger must return to zero
    for o in list(active):
        mm._settle(BinaryOption(legs=o.legs, option_id=o.option_id, steps_until_expiry=0,
                                strike=o.strike), vals)
    return {"min_free": min_free, "max_util": max_util, "trades": trades,
            "residual_lock": mm._locked,
            "residual_risk": float(max((abs(x) for x in mm._net_lots.values()), default=0)),
            "pnl": mm._free - cash}


def main() -> None:
    fails = 0
    for label, toxic in (("BENIGN", False), ("TOXIC", True)):
        stats = [run_session(s, cash, toxic)
                 for s in range(400) for cash in ([10.0, 20.0, 40.0][s % 3],)]
        insolvent = [s for s in stats if s["min_free"] < -1e-9]
        leaks = [s for s in stats if abs(s["residual_lock"]) > 1e-6 or s["residual_risk"] > 1e-6]
        pnls = sorted(s["pnl"] for s in stats)
        print(f"{label:>7}: n={len(stats)}  insolvent={len(insolvent)}  ledger_leaks={len(leaks)}  "
              f"maxutil={max(s['max_util'] for s in stats):.2f}  "
              f"trades/sess={sum(s['trades'] for s in stats) / len(stats):.1f}  "
              f"pnl p05={pnls[len(pnls) // 20]:+.2f} med={pnls[len(pnls) // 2]:+.2f} "
              f"p95={pnls[-len(pnls) // 20]:+.2f}")
        fails += len(insolvent) + len(leaks)
    print("ALL PASS" if fails == 0 else f"{fails} FAILURES")
    sys.exit(0 if fails == 0 else 1)


if __name__ == "__main__":
    main()
