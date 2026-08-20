"""Is our sigma_eps calibrated? Compare it to the ACTUAL theo error after a warm-up.

Draws true MarketParameters, simulates a warm-up, runs the real estimator, then
measures |estimated theo - true theo| against the sigma_eps we report, bucketed by
moneyness. Decides whether the sigma floor in quote() is too conservative.
"""
import math
import os
import random
import sys
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Market_Maker_2 import (  # noqa: E402
    AJARAI_UNDERLYING_ID, FED_FUNDS_RATE_UNDERLYING_ID, THERIODIC_UNDERLYING_ID,
    BinaryOption, MarketHistory, MarketMaker, MarketParameters, OptionLeg, Underlying,
    _Law, _Model, _price, _safe_rho, _sigma_eps,
)


def true_model(mp: MarketParameters) -> _Model:
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


def draw_params(rng: random.Random) -> MarketParameters:
    return MarketParameters(
        ajarai_drift=rng.uniform(-0.002, 0.002), ajarai_idio_std_dev=rng.uniform(0.008, 0.05),
        ajarai_rate_beta=-abs(rng.uniform(0.0, 0.2)), ajarai_sector_beta=rng.uniform(0.5, 2.0),
        rate_down_probability=rng.uniform(0.15, 0.4), rate_reversion_strength=rng.uniform(0.0, 0.3),
        rate_up_probability=rng.uniform(0.15, 0.4), sector_std_dev=rng.uniform(0.008, 0.025),
        theriodic_drift=rng.uniform(-0.002, 0.002), theriodic_idio_std_dev=rng.uniform(0.008, 0.05),
        theriodic_rate_beta=-abs(rng.uniform(0.0, 0.2)), theriodic_sector_beta=rng.uniform(0.5, 2.0))


def step(mp: MarketParameters, v: dict, rng: random.Random) -> dict:
    r = v[FED_FUNDS_RATE_UNDERLYING_ID]
    tilt = mp.rate_reversion_strength * (mp.rate_target - r)
    up = min(max(mp.rate_up_probability + tilt, 0.0), 1.0)
    down = min(max(mp.rate_down_probability - tilt, 0.0), 1.0 - up)
    u = rng.random()
    nr = round(r + mp.rate_step, 2) if u < up else (round(r - mp.rate_step, 2) if u < up + down else r)
    nr = max(nr, 0.0)
    rc = round(nr - r, 2)
    sec = rng.gauss(0.0, mp.sector_std_dev)
    a = v[AJARAI_UNDERLYING_ID] * math.exp(
        mp.ajarai_drift + mp.ajarai_rate_beta * rc + mp.ajarai_sector_beta * sec
        + rng.gauss(0.0, mp.ajarai_idio_std_dev))
    t = v[THERIODIC_UNDERLYING_ID] * math.exp(
        mp.theriodic_drift + mp.theriodic_rate_beta * rc + mp.theriodic_sector_beta * sec
        + rng.gauss(0.0, mp.theriodic_idio_std_dev))
    return {FED_FUNDS_RATE_UNDERLYING_ID: nr, AJARAI_UNDERLYING_ID: round(a, 2),
            THERIODIC_UNDERLYING_ID: round(t, 2)}


def main() -> None:
    for n_warm in (18, 30, 60):
        buckets: dict[str, list[tuple[float, float]]] = {"deep(<.15/>.85)": [], "mid": [], "ATM(.35-.65)": []}
        for trial in range(300):
            rng = random.Random(50000 + trial)
            mp = draw_params(rng)
            v = {FED_FUNDS_RATE_UNDERLYING_ID: max(round(rng.uniform(0.5, 5.0) * 4) / 4, 0.0),
                 AJARAI_UNDERLYING_ID: round(rng.uniform(400, 1500), 2),
                 THERIODIC_UNDERLYING_ID: round(rng.uniform(400, 1500), 2)}
            hist = {k: [x] for k, x in v.items()}
            for _ in range(n_warm - 1):
                v = step(mp, v, rng)
                for k in hist:
                    hist[k].append(v[k])
            unds = [Underlying("FED", 1, v[1]), Underlying("AJR", 2, v[2]), Underlying("THR", 3, v[3])]
            mm = MarketMaker(unds, [], 100.0)
            mm.warm_up(MarketHistory(values_by_underlying_id={k: tuple(x) for k, x in hist.items()}))
            if mm._model is None:
                continue
            tm = true_model(mp)
            for oi in range(8):
                steps = rng.choice([1, 2, 3, 5])
                kind = rng.random()
                if kind < 0.35:
                    opt = BinaryOption(legs=(OptionLeg(1, 1.0),), option_id=oi,
                                       steps_until_expiry=steps,
                                       strike=max(round((v[1] + 0.25 * rng.randint(-3, 3)) * 4) / 4, 0.0))
                elif kind < 0.85:
                    u = rng.choice([2, 3])
                    opt = BinaryOption(legs=(OptionLeg(u, 1.0),), option_id=oi,
                                       steps_until_expiry=steps,
                                       strike=round(v[u] * math.exp(rng.gauss(0, 0.06)), 2))
                else:
                    w = rng.choice([1.0, -1.0])
                    opt = BinaryOption(legs=(OptionLeg(2, w), OptionLeg(3, -w)), option_id=oi,
                                       steps_until_expiry=steps, strike=0.0)
                p_true = _price(tm, opt, v)
                p_est = _price(mm._model, opt, v)
                sig = _sigma_eps(mm._model, opt, v)
                key = ("deep(<.15/>.85)" if p_true < 0.15 or p_true > 0.85
                       else "ATM(.35-.65)" if 0.35 <= p_true <= 0.65 else "mid")
                buckets[key].append((abs(p_est - p_true), sig))

        print(f"=== warm-up {n_warm} days ===")
        print(f"{'bucket':>18}{'n':>6}{'mean|err|':>11}{'mean sig':>10}{'sig/err':>9}"
              f"{'P(|e|>1.0s)':>13}{'P(|e|>0.7s)':>13}{'P(|e|>0.5s)':>13}")
        for key, rows in buckets.items():
            if not rows:
                continue
            errs = [e for e, _ in rows]
            sigs = [s for _, s in rows]
            cov = lambda k: sum(1 for e, s in rows if e > k * s) / len(rows)  # noqa: E731
            print(f"{key:>18}{len(rows):>6}{mean(errs):>11.4f}{mean(sigs):>10.4f}"
                  f"{mean(sigs) / max(mean(errs), 1e-9):>9.2f}"
                  f"{cov(1.0):>13.3f}{cov(0.7):>13.3f}{cov(0.5):>13.3f}")
        print()


if __name__ == "__main__":
    main()
