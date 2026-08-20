"""Instrumented map of the LIVE policy surface.

Runs realistic sessions and records, for every quote and FOK, which branch of the
policy actually bound. The point is to separate the parameters that decide our
behaviour from the ones that are decorative.
"""
import math
import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calibrate_sigma as cal  # noqa: E402
from Market_Maker_2 import (  # noqa: E402
    BinaryOption, FokOrder, MarketHistory, MarketMaker, MarketParameters, OptionLeg,
    OrderType, Underlying, _price, _sigma_eps,
)


def draw_real(rng: random.Random) -> MarketParameters:
    """Parameter draw anchored on Test Case 1, the only printed ground truth."""
    return MarketParameters(
        ajarai_drift=rng.uniform(-0.003, 0.003), ajarai_idio_std_dev=rng.uniform(0.006, 0.025),
        ajarai_rate_beta=-abs(rng.uniform(0.0, 0.05)), ajarai_sector_beta=rng.uniform(0.6, 1.6),
        rate_down_probability=rng.uniform(0.12, 0.35), rate_reversion_strength=rng.uniform(0.0, 0.25),
        rate_up_probability=rng.uniform(0.12, 0.35), sector_std_dev=rng.uniform(0.01, 0.03),
        theriodic_drift=rng.uniform(-0.003, 0.003), theriodic_idio_std_dev=rng.uniform(0.006, 0.025),
        theriodic_rate_beta=-abs(rng.uniform(0.0, 0.05)), theriodic_sector_beta=rng.uniform(0.6, 1.6))

W = Counter()      # what set the half-width
CLS = Counter()    # counterparty class at quote time
SZ = Counter()     # what set the quote size
SKEW = Counter()
FOK = Counter()
MISC = Counter()


def probe_quote(mm: MarketMaker, opt: BinaryOption, cp: int) -> None:
    cls = mm._class_of(cp)
    CLS[cls] += 1
    values = {u.underlying_id: u.value for u in mm.underlying_state}
    theo = _price(mm._the_model(), opt, values)
    sig = _sigma_eps(mm._the_model(), opt, values)
    util = mm._utilization()
    base_const = MarketMaker.BASE_EDGE[cls]
    sig_mult = 2.0 if cls == "INFORMED" else 1.0
    W["sigma floor binds" if sig_mult * sig > base_const else "BASE_EDGE binds"] += 1
    charge = MarketMaker.CAPITAL_WIDEN * util
    base = max(base_const, sig_mult * sig)
    if charge * max(theo, 1 - theo) > 0.25 * base:
        W["capital charge material (>25% of base)"] += 1

    raw_skew = MarketMaker.SKEW_PER_LOT * mm._net_dir_lots(opt)
    if raw_skew == 0:
        SKEW["flat (no skew)"] += 1
    elif abs(raw_skew) >= MarketMaker.SKEW_CAP:
        SKEW["skew CAPPED"] += 1
    else:
        SKEW["skew active, uncapped"] += 1

    q = mm.quote(opt, cp)
    if util > MarketMaker.MAX_LOCKED_FRAC:
        MISC["MAX_LOCKED_FRAC throttle fired"] += 1
    budget = MarketMaker.QUOTE_LOCK_FRAC[cls] * max(mm._free, 0.0)
    for side, price, qty in (("bid", q.bid_price, q.bid_quantity),
                             ("offer", 1.0 - q.offer_price, q.offer_quantity)):
        if qty >= MarketMaker.FREE_ROLL_SIZE:
            SZ[f"{side}: FREE_ROLL (zero lock)"] += 1
        elif qty >= MarketMaker.SIZE_CAP:
            SZ[f"{side}: SIZE_CAP 40"] += 1
        elif qty <= 1:
            SZ[f"{side}: floored at 1 lot"] += 1
        else:
            SZ[f"{side}: budget-limited"] += 1
    _ = budget


def probe_fok(mm: MarketMaker, opt: BinaryOption, f: FokOrder) -> bool:
    values = {u.underlying_id: u.value for u in mm.underlying_state}
    theo = _price(mm._the_model(), opt, values)
    sig = _sigma_eps(mm._the_model(), opt, values)
    cls = mm._class_of(f.counterparty_id)
    if f.order_type is OrderType.BUY:
        edge, lock_per = f.price - theo, 1.0 - f.price
    else:
        edge, lock_per = theo - f.price, f.price
    lock = f.quantity * lock_per
    steps = max(opt.steps_until_expiry, 1)
    accepted = mm.respond_to_fok(opt, f)
    if accepted:
        FOK["ACCEPTED"] += 1
    elif edge < max(MarketMaker.FOK_FLOOR[cls], MarketMaker.FOK_SIG[cls] * sig):
        FOK["reject: edge below floor/sigma"] += 1
    elif lock > MarketMaker.FOK_LOCK_FRAC * max(mm._free, 0.0):
        FOK["reject: lock > 20% free"] += 1
    elif (mm._free - lock) < MarketMaker.MIN_FREE_FRAC * mm._cash0:
        FOK["reject: post-trade free < 40%"] += 1
    elif lock_per > 1e-9 and edge / lock_per < MarketMaker.ROI_PER_DAY * steps:
        FOK["reject: ROI-per-day floor"] += 1
    else:
        FOK["reject: other"] += 1
    return accepted


def session(seed: int, cash: float, toxic: bool) -> None:
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
    for _ in range(25):
        for _ in range(rng.randint(1, 4)):
            opt = rng.choice(active)
            cp = rng.randint(100000, 999999) if rng.random() < 0.8 else rng.randint(1, 5)
            probe_quote(mm, opt, cp)
            if rng.random() < 0.45:
                q = mm.quote(opt, cp)
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
            if probe_fok(mm, opt, f):
                mm.on_trade(opt, f.price, -f.quantity if f.order_type is OrderType.BUY else f.quantity, cp)
        v[1] = max(round(v[1] + rng.choice([-0.25, 0.0, 0.25]), 2), 0.0)
        v[2] = round(v[2] * math.exp(rng.gauss(0, 0.02)), 2)
        v[3] = round(v[3] * math.exp(rng.gauss(0, 0.03)), 2)
        nxt = [o.advance_step() for o in active]
        nxt = [o for o in nxt if o.steps_until_expiry > 0]
        while len(nxt) < 5:
            nxt.append(mk(rng.randint(1, 5)))
        mm.on_step_advance([Underlying("FED", 1, v[1]), Underlying("AJR", 2, v[2]),
                            Underlying("THR", 3, v[3])], nxt)
        active = [o for o in nxt if o.steps_until_expiry > 0]


for s in range(120):
    session(7000 + s, [10.0, 20.0, 40.0][s % 3], toxic=(s % 2 == 0))


def show(title, ctr):
    tot = sum(ctr.values()) or 1
    print(f"\n{title}")
    for k, n in ctr.most_common():
        print(f"    {n / tot:>6.1%}  {k}   (n={n})")


show("COUNTERPARTY CLASS at quote time", CLS)
show("WHAT SETS THE HALF-WIDTH", W)
show("INVENTORY SKEW STATE", SKEW)
show("WHAT SETS QUOTE SIZE", SZ)
show("FOK OUTCOMES", FOK)
show("THROTTLES", MISC)
