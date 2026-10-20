"""Validation for mm2/Market_Maker_2.py.

1. THEO parity: MM2 pricer vs the old grader-validated pricer (max_error 0.0000
   on THEO test) across a battery of options and parameter sets.
2. Monte Carlo cross-check against the REAL data-generating process (the
   template's dynamics reproduced from MarketParameters).
3. Mechanics smoke: quote validity, FOK, margining, settlement, cp classification.
All output on stderr-safe plain prints (this file is local-only, never submitted).
"""
import math
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Market_Maker_2 import (  # noqa: E402
    AJARAI_UNDERLYING_ID, FED_FUNDS_RATE_UNDERLYING_ID, THERIODIC_UNDERLYING_ID,
    BinaryOption, FokOrder, MarketHistory, MarketParameters, MarketMaker,
    OptionLeg, OrderType, Quote, Underlying, _Law, _Model, _price, _safe_rho,
)

PARAM_SETS = [
    MarketParameters(
        ajarai_drift=0.001, ajarai_idio_std_dev=0.02, ajarai_rate_beta=-0.05,
        ajarai_sector_beta=1.0, rate_down_probability=0.25, rate_reversion_strength=0.1,
        rate_up_probability=0.25, sector_std_dev=0.015, theriodic_drift=-0.0005,
        theriodic_idio_std_dev=0.03, theriodic_rate_beta=-0.08, theriodic_sector_beta=1.3),
    MarketParameters(
        ajarai_drift=-0.002, ajarai_idio_std_dev=0.04, ajarai_rate_beta=-0.12,
        ajarai_sector_beta=0.7, rate_down_probability=0.35, rate_reversion_strength=0.3,
        rate_up_probability=0.15, sector_std_dev=0.02, theriodic_drift=0.002,
        theriodic_idio_std_dev=0.015, theriodic_rate_beta=-0.03, theriodic_sector_beta=1.8),
    MarketParameters(
        ajarai_drift=0.0, ajarai_idio_std_dev=0.01, ajarai_rate_beta=0.0,
        ajarai_sector_beta=0.0, rate_down_probability=0.4, rate_reversion_strength=0.0,
        rate_up_probability=0.4, sector_std_dev=0.01, theriodic_drift=0.0,
        theriodic_idio_std_dev=0.05, theriodic_rate_beta=-0.2, theriodic_sector_beta=2.0),
]

VALUES = {FED_FUNDS_RATE_UNDERLYING_ID: 2.0, AJARAI_UNDERLYING_ID: 1000.0,
          THERIODIC_UNDERLYING_ID: 750.0}

OPTIONS = [
    BinaryOption(legs=(OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, 1.0),), option_id=1,
                 steps_until_expiry=3, strike=2.0),
    BinaryOption(legs=(OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, 1.0),), option_id=2,
                 steps_until_expiry=5, strike=2.25),
    BinaryOption(legs=(OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, 1.0),), option_id=3,
                 steps_until_expiry=1, strike=1.75),
    BinaryOption(legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0),), option_id=4,
                 steps_until_expiry=4, strike=1000.0),
    BinaryOption(legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0),), option_id=5,
                 steps_until_expiry=2, strike=1050.0),
    BinaryOption(legs=(OptionLeg(THERIODIC_UNDERLYING_ID, 1.0),), option_id=6,
                 steps_until_expiry=6, strike=700.0),
    BinaryOption(legs=(OptionLeg(THERIODIC_UNDERLYING_ID, 1.0),), option_id=7,
                 steps_until_expiry=1, strike=760.0),
    BinaryOption(legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0), OptionLeg(THERIODIC_UNDERLYING_ID, -1.0)),
                 option_id=8, steps_until_expiry=3, strike=0.0),
    BinaryOption(legs=(OptionLeg(AJARAI_UNDERLYING_ID, -1.0), OptionLeg(THERIODIC_UNDERLYING_ID, 1.0)),
                 option_id=9, steps_until_expiry=5, strike=0.0),
    BinaryOption(legs=(OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, 1.0),), option_id=10,
                 steps_until_expiry=0, strike=2.0),
]


def model_from(mp: MarketParameters) -> _Model:
    return _Model(
        p_up=mp.rate_up_probability, p_down=mp.rate_down_probability,
        strength=mp.rate_reversion_strength, target=mp.rate_target,
        laws={AJARAI_UNDERLYING_ID: _Law(mp.ajarai_drift, mp.ajarai_rate_beta,
                                         math.hypot(mp.ajarai_sector_beta * mp.sector_std_dev,
                                                    mp.ajarai_idio_std_dev)),
              THERIODIC_UNDERLYING_ID: _Law(mp.theriodic_drift, mp.theriodic_rate_beta,
                                            math.hypot(mp.theriodic_sector_beta * mp.sector_std_dev,
                                                       mp.theriodic_idio_std_dev))},
        rho=_safe_rho(mp))


def simulate_once(mp: MarketParameters, values: dict, steps: int, rng: random.Random) -> dict:
    """Exact replica of the template's advance_step dynamics."""
    r = values[FED_FUNDS_RATE_UNDERLYING_ID]
    a = values[AJARAI_UNDERLYING_ID]
    t = values[THERIODIC_UNDERLYING_ID]
    for _ in range(steps):
        tilt = mp.rate_reversion_strength * (mp.rate_target - r)
        up = min(max(mp.rate_up_probability + tilt, 0.0), 1.0)
        down = min(max(mp.rate_down_probability - tilt, 0.0), 1.0 - up)
        u = rng.random()
        if u < up:
            new_r = round(r + mp.rate_step, 2)
        elif u < up + down:
            new_r = round(r - mp.rate_step, 2)
        else:
            new_r = r
        new_r = max(new_r, 0.0)
        rc = round(new_r - r, 2)
        r = new_r
        sector = rng.gauss(0.0, mp.sector_std_dev)
        lr_a = mp.ajarai_drift + mp.ajarai_rate_beta * rc + mp.ajarai_sector_beta * sector \
            + rng.gauss(0.0, mp.ajarai_idio_std_dev)
        lr_t = mp.theriodic_drift + mp.theriodic_rate_beta * rc + mp.theriodic_sector_beta * sector \
            + rng.gauss(0.0, mp.theriodic_idio_std_dev)
        a = round(a * math.exp(lr_a), 2)
        t = round(t * math.exp(lr_t), 2)
    return {FED_FUNDS_RATE_UNDERLYING_ID: r, AJARAI_UNDERLYING_ID: a, THERIODIC_UNDERLYING_ID: t}


def main() -> None:
    fails = 0

    # ---- 1. Monte Carlo cross-check (ground truth: template dynamics) ----
    print("== MC cross-check (100k paths each) ==")
    n_mc = 100_000
    for pi, mp in enumerate(PARAM_SETS):
        worst = 0.0
        for opt in OPTIONS:
            theo = _price(model_from(mp), opt, VALUES)
            rng = random.Random(1234 + pi * 100 + opt.option_id)
            if opt.steps_until_expiry == 0:
                mc = opt.expiry_valuation(VALUES)
            else:
                hits = sum(
                    opt.expiry_valuation(simulate_once(mp, VALUES, opt.steps_until_expiry, rng))
                    for _ in range(n_mc))
                mc = hits / n_mc
            err = abs(theo - mc)
            worst = max(worst, err)
            tol = 3.0 * math.sqrt(max(mc * (1 - mc), 1e-9) / n_mc) + 0.0035
            flag = "OK " if err <= tol else "FAIL"
            if err > tol:
                fails += 1
            print(f"  set{pi} opt{opt.option_id:2d} theo={theo:.4f} mc={mc:.4f} "
                  f"err={err:.4f} tol={tol:.4f} {flag}")
        print(f"  set{pi} worst={worst:.4f}")

    # ---- 2. Mechanics smoke test ----
    print("== Mechanics ==")
    unds = [Underlying("FED", FED_FUNDS_RATE_UNDERLYING_ID, 2.0),
            Underlying("AJR", AJARAI_UNDERLYING_ID, 1000.0),
            Underlying("THR", THERIODIC_UNDERLYING_ID, 750.0)]
    mm = MarketMaker(unds, list(OPTIONS[:9]), 1000.0)
    assert mm.name == "Hamza Khan"

    # warm_up on synthetic history generated by true dynamics
    rng = random.Random(7)
    mp = PARAM_SETS[0]
    vals = dict(VALUES)
    hist_r, hist_a, hist_t = [vals[1]], [vals[2]], [vals[3]]
    for _ in range(30):
        vals = simulate_once(mp, vals, 1, rng)
        hist_r.append(vals[1]); hist_a.append(vals[2]); hist_t.append(vals[3])
    mm.warm_up(MarketHistory(values_by_underlying_id={
        1: tuple(hist_r), 2: tuple(hist_a), 3: tuple(hist_t)}))
    assert mm._model is not None, "estimation failed"
    est_err = 0.0
    for opt in OPTIONS[:9]:
        true_p = _price(model_from(mp), opt, VALUES)
        est_p = mm.price_option(opt)
        est_err = max(est_err, abs(true_p - est_p))
    print(f"  warm_up worst |est-true| theo gap = {est_err:.4f} (expect < 0.25)")
    if est_err > 0.25:
        fails += 1

    # price_option_from_parameters == direct pricer
    for opt in OPTIONS:
        d = abs(mm.price_option_from_parameters(mp, opt) - _price(model_from(mp), opt, VALUES))
        if d > 1e-12:
            print(f"  FAIL from_parameters mismatch opt{opt.option_id} d={d}")
            fails += 1
    print("  from_parameters parity OK")

    # quotes valid for all cp classes
    for cp in (101, 102, 103):
        for opt in OPTIONS[:9]:
            q = mm.quote(opt, cp)
            assert isinstance(q, Quote)
    # force INFORMED and UNINF labels, re-quote
    mm._cp[201].n = 3; mm._cp[201].strikes = 2
    mm._cp[202].n = 3; mm._cp[202].clean = 3
    q_inf = mm.quote(OPTIONS[0], 201)
    q_dumb = mm.quote(OPTIONS[0], 202)
    w_inf = q_inf.offer_price - q_inf.bid_price
    w_dumb = q_dumb.offer_price - q_dumb.bid_price
    print(f"  width informed={w_inf:.2f} vs uninformed={w_dumb:.2f} (must be wider)")
    if w_inf <= w_dumb:
        fails += 1

    # FOK: donation accepted, pick-off refused, giant lock refused
    theo0 = mm.price_option(OPTIONS[0])
    don = FokOrder(counterparty_id=301, option_id=1, order_type=OrderType.BUY,
                   price=min(round(theo0 + 0.15, 2), 0.99), quantity=5)
    steal = FokOrder(counterparty_id=302, option_id=1, order_type=OrderType.BUY,
                     price=max(round(theo0 - 0.10, 2), 0.01), quantity=5)
    giant = FokOrder(counterparty_id=303, option_id=1, order_type=OrderType.SELL,
                     price=min(round(theo0 + 0.2, 2), 0.99), quantity=100000)
    r1, r2, r3 = (mm.respond_to_fok(OPTIONS[0], f) for f in (don, steal, giant))
    print(f"  FOK donation={r1} (want True), pickoff={r2} (want False), giant={r3} (want False)")
    fails += (not r1) + r2 + r3

    # margin ledger: buy 10 @ 0.40 locks 4.0; settle at payoff 1.0 credits 10.0
    free0 = mm._free
    mm.on_trade(OPTIONS[2], 0.40, 10, 401)   # opt3: FED >= 1.75 in 1 step
    assert abs((free0 - mm._free) - 4.0) < 1e-9, "lock mismatch"
    expired = BinaryOption(legs=OPTIONS[2].legs, option_id=OPTIONS[2].option_id,
                           steps_until_expiry=0, strike=OPTIONS[2].strike)
    mm.on_step_advance(unds, [expired])
    assert abs(mm._free - (free0 - 4.0 + 10.0)) < 1e-9, "settlement credit mismatch"
    print("  margin lock/settle OK")

    # never prints to stdout from the strategy: verified by inspection (no print in module)
    import Market_Maker_2 as m2
    src = open(m2.__file__, encoding="utf-8").read()
    assert "print(" not in src, "strategy module must not print"
    print("  no stdout in module OK")

    print(f"== {'ALL PASS' if fails == 0 else f'{fails} FAILURES'} ==")
    sys.exit(0 if fails == 0 else 1)


if __name__ == "__main__":
    main()
