"""Validate the live MarketMaker pricer against Monte Carlo of the ACTUAL simulator.

Uses MarketParameters.advance_step itself as ground truth, so any mismatch is ours.
"""
import math
import random
import statistics

from Market_Maker import (
    AJARAI_UNDERLYING_ID,
    FED_FUNDS_RATE_UNDERLYING_ID,
    THERIODIC_UNDERLYING_ID,
    BinaryOption,
    MarketHistory,
    MarketMaker,
    MarketParameters,
    OptionLeg,
    Underlying,
)

FED, AJR, THR = FED_FUNDS_RATE_UNDERLYING_ID, AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID

TRUE_PARAMS = MarketParameters(
    ajarai_drift=0.001,
    ajarai_idio_std_dev=0.020,
    ajarai_rate_beta=-0.08,
    ajarai_sector_beta=1.2,
    rate_down_probability=0.25,
    rate_reversion_strength=0.10,
    rate_up_probability=0.25,
    sector_std_dev=0.015,
    theriodic_drift=-0.0005,
    theriodic_idio_std_dev=0.025,
    theriodic_rate_beta=-0.05,
    theriodic_sector_beta=0.8,
)

START = {FED: 2.5, AJR: 150.0, THR: 900.0}
MAX_STEPS = 6
N_PATHS = 300_000


def leg(uid: int, w: float = 1.0) -> OptionLeg:
    return OptionLeg(underlying_id=uid, weight=w)


BATTERY: list[BinaryOption] = [
    BinaryOption(legs=(leg(FED),), option_id=1, steps_until_expiry=5, strike=2.5),      # ATM on-grid (tie mass!)
    BinaryOption(legs=(leg(FED),), option_id=2, steps_until_expiry=3, strike=3.0),      # OTM
    BinaryOption(legs=(leg(FED, -1.0),), option_id=3, steps_until_expiry=4, strike=-2.0),  # FED <= 2.0
    BinaryOption(legs=(leg(AJR),), option_id=4, steps_until_expiry=5, strike=160.0),    # company OTM
    BinaryOption(legs=(leg(THR),), option_id=5, steps_until_expiry=2, strike=850.0),    # company ITM
    BinaryOption(legs=(leg(AJR), leg(THR, -0.2)), option_id=6, steps_until_expiry=4, strike=0.0),   # spread OTM
    BinaryOption(legs=(leg(AJR), leg(THR, -1.0 / 6.0)), option_id=7, steps_until_expiry=4, strike=0.0),  # spread ATM
    BinaryOption(legs=(leg(FED, 10.0), leg(AJR)), option_id=8, steps_until_expiry=3, strike=185.0),  # mixed FED+co
    BinaryOption(legs=(leg(AJR), leg(THR, 0.1)), option_id=9, steps_until_expiry=4, strike=250.0),   # same-sign quad
    BinaryOption(legs=(leg(THR),), option_id=10, steps_until_expiry=6, strike=2000.0),  # deep OTM
    BinaryOption(legs=(leg(AJR),), option_id=11, steps_until_expiry=1, strike=150.0),   # 1-day ATM
]


def simulate_paths(params: MarketParameters, start: dict[int, float], steps: int, n: int, seed: int):
    random.seed(seed)
    frames = [[] for _ in range(steps + 1)]
    for _ in range(n):
        values = dict(start)
        frames[0].append(dict(values))
        for s in range(1, steps + 1):
            values = params.advance_step(values)
            frames[s].append(dict(values))
    return frames


def make_mm() -> MarketMaker:
    underlyings = [
        Underlying(name="FED", underlying_id=FED, value=START[FED]),
        Underlying(name="AJR", underlying_id=AJR, value=START[AJR]),
        Underlying(name="THR", underlying_id=THR, value=START[THR]),
    ]
    return MarketMaker(underlying_initial_state=underlyings, option_initial_state=list(BATTERY), cash_balance=1000.0)


def main() -> None:
    MarketMaker.TELEMETRY = False
    print("=== Simulating ground truth (actual MarketParameters.advance_step) ===")
    frames = simulate_paths(TRUE_PARAMS, START, MAX_STEPS, N_PATHS, seed=42)
    mm = make_mm()

    print("\n=== TEST A: price_option_from_parameters (THEO test) vs Monte Carlo ===")
    failures = 0
    for option in BATTERY:
        model_price = mm.price_option_from_parameters(TRUE_PARAMS, option)
        payoffs = [option.expiry_valuation(v) for v in frames[option.steps_until_expiry]]
        mc_price = statistics.fmean(payoffs)
        se = math.sqrt(max(mc_price * (1 - mc_price), 1e-12) / len(payoffs))
        tol = max(4 * se, 0.004)  # 4 MC sigmas or 0.4c, whichever is larger (value-rounding slack)
        ok = abs(model_price - mc_price) <= tol
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  [{option.option_id:>2}] {str(option):<48} model={model_price:.4f} mc={mc_price:.4f} diff={abs(model_price-mc_price):.4f} tol={tol:.4f}")

    print("\n=== TEST B: warm_up estimation -> price_option vs true-parameter prices ===")
    random.seed(123)
    hist_values = {FED: [2.0], AJR: [100.0], THR: [800.0]}
    values = {FED: 2.0, AJR: 100.0, THR: 800.0}
    for _ in range(1500):
        values = TRUE_PARAMS.advance_step(values)
        for uid in (FED, AJR, THR):
            hist_values[uid].append(values[uid])
    history = MarketHistory(values_by_underlying_id={k: tuple(v) for k, v in hist_values.items()})
    mm2 = make_mm()
    mm2.warm_up(history)
    est_fail = 0
    for option in BATTERY:
        true_price = mm2.price_option_from_parameters(TRUE_PARAMS, option)
        est_price = mm2.price_option(option)
        ok = abs(true_price - est_price) <= 0.05  # estimation error budget on 1500 days
        est_fail += not ok
        print(f"{'PASS' if ok else 'FAIL'}  [{option.option_id:>2}] true={true_price:.4f} est={est_price:.4f} diff={abs(true_price-est_price):.4f}")

    print("\n=== TEST C: quote/respond_to_fok mechanics (validity, no exceptions) ===")
    from Market_Maker import FokOrder, OrderType

    mech_fail = 0
    for option in BATTERY:
        try:
            qt = mm2.quote(option, counterparty_id=7)
            assert 0.0 <= qt.bid_price < qt.offer_price <= 1.0
            theo = mm2.price_option(option)
            assert qt.bid_price <= theo + 0.02 and qt.offer_price >= theo - 0.02
        except Exception as exc:
            mech_fail += 1
            print(f"FAIL  quote [{option.option_id}] raised/violated: {exc}")
    for price, otype in ((0.99, OrderType.SELL), (0.01, OrderType.BUY), (0.50, OrderType.BUY)):
        try:
            fok = FokOrder(counterparty_id=3, option_id=7, order_type=otype, price=price, quantity=5)
            mm2.respond_to_fok(BATTERY[6], fok)
        except Exception as exc:
            mech_fail += 1
            print(f"FAIL  respond_to_fok({otype},{price}) raised: {exc}")
    fok_cheap = FokOrder(counterparty_id=3, option_id=7, order_type=OrderType.SELL, price=0.01, quantity=5)
    fok_rich = FokOrder(counterparty_id=3, option_id=7, order_type=OrderType.BUY, price=0.99, quantity=5)
    buy_cheap = mm2.respond_to_fok(BATTERY[6], fok_cheap)   # counterparty sells at 0.01 -> we should buy
    sell_rich = mm2.respond_to_fok(BATTERY[6], fok_rich)    # counterparty buys at 0.99 -> we should sell
    print(f"{'PASS' if buy_cheap else 'FAIL'}  accepts obviously cheap FOK (buy @0.01)")
    print(f"{'PASS' if sell_rich else 'FAIL'}  accepts obviously rich FOK (sell @0.99)")
    mech_fail += (not buy_cheap) + (not sell_rich)
    print(f"quote mechanics failures: {mech_fail}")

    total_fail = failures + est_fail + mech_fail
    print(f"\n{'ALL LIVE CHECKS PASSED' if total_fail == 0 else f'*** {total_fail} FAILURES ***'}")


if __name__ == "__main__":
    main()
