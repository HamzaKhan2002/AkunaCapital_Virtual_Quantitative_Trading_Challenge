"""Hunt for inputs that silently trip the exception fallbacks in Market_Maker_2.py.

Every public method is wrapped in try/except returning a degenerate default
(Quote(0.0,1,1.0,1), price 0.5, reject-all). If some realistic input shape
reliably crashes the REAL logic, tuning anything else would be invisible in
that session -- exactly the "mechanical/edge case" pattern to hunt for.

Strategy: call the INTERNAL logic directly (bypassing the try/except) so any
exception surfaces instead of being swallowed, across a wide battery of
realistic-to-adversarial inputs pulled from the official spec's stated ranges
plus edge cases (very short warm-ups, boundary values, unusual option shapes).
"""
import math
import os
import random
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Market_Maker_2 import (  # noqa: E402
    AJARAI_UNDERLYING_ID, FED_FUNDS_RATE_UNDERLYING_ID, THERIODIC_UNDERLYING_ID,
    BinaryOption, FokOrder, MarketHistory, MarketMaker, OptionLeg, OrderType, Underlying,
    _price, _sigma_eps,
)

fails = []


def probe(label, fn):
    try:
        fn()
    except Exception:
        fails.append((label, traceback.format_exc(limit=3)))


unds_normal = [Underlying("FED", 1, 2.0), Underlying("AJR", 2, 1000.0), Underlying("THR", 3, 750.0)]

# ---- warm_up edge cases ----
HIST_CASES = {
    "empty": {},
    "1 day": {1: (2.0,), 2: (1000.0,), 3: (750.0,)},
    "2 days": {1: (2.0, 2.0), 2: (1000.0, 1000.0), 3: (750.0, 750.0)},
    "3 days": {1: (2.0, 2.25, 2.0), 2: (1000.0, 1010.0, 995.0), 3: (750.0, 745.0, 760.0)},
    "all-flat (zero variance)": {1: tuple([2.0] * 20), 2: tuple([1000.0] * 20), 3: tuple([750.0] * 20)},
    "AJR hits zero mid-history": {1: tuple([2.0] * 20), 2: (1000.0,) * 5 + (0.0,) + (1000.0,) * 14,
                                  3: tuple([750.0] * 20)},
    "negative value present": {1: tuple([2.0] * 10), 2: (1000.0,) * 5 + (-50.0,) + (1000.0,) * 4,
                              3: tuple([750.0] * 10)},
    "rate at 0 the whole time": {1: tuple([0.0] * 20), 2: tuple([1000.0] * 20), 3: tuple([750.0] * 20)},
    "huge rate swings": {1: tuple(6.0 if i % 2 == 0 else 0.0 for i in range(20)),
                        2: tuple([1000.0] * 20), 3: tuple([750.0] * 20)},
    "mismatched lengths": {1: (2.0, 2.0, 2.0), 2: (1000.0,), 3: (750.0, 750.0)},
    "missing an underlying entirely": {1: tuple([2.0] * 10), 2: tuple([1000.0] * 10)},
    "extreme AJR magnitude": {1: tuple([2.0] * 10), 2: tuple([1e12] * 10), 3: tuple([750.0] * 10)},
    "tiny AJR magnitude": {1: tuple([2.0] * 10), 2: tuple([0.01] * 10), 3: tuple([750.0] * 10)},
    "60 days realistic": {1: tuple(round(max(2.0 + 0.25 * random.Random(1).randint(-2, 2), 0.0), 2)
                                  for _ in range(60)),
                          2: tuple(round(1000 * math.exp(random.Random(2).gauss(0, 0.02) * i), 2)
                                   for i in range(60)),
                          3: tuple(round(750 * math.exp(random.Random(3).gauss(0, 0.03) * i), 2)
                                   for i in range(60))},
}
for label, hist in HIST_CASES.items():
    def fn(h=hist):
        mm = MarketMaker(unds_normal, [], 20.0)
        model = mm._estimate(MarketHistory(values_by_underlying_id=h))  # UNWRAPPED: raises if buggy
        assert model is None or model.n_obs > 0
    probe(f"warm_up/_estimate: {label}", fn)

# ---- option shapes beyond the guaranteed spec ----
OPT_CASES = {
    "FED weight=2, off-grid strike": BinaryOption(legs=(OptionLeg(1, 2.0),), option_id=1,
                                                  steps_until_expiry=3, strike=3.1415),
    "FED weight=-1": BinaryOption(legs=(OptionLeg(1, -1.0),), option_id=2,
                                  steps_until_expiry=3, strike=-2.0),
    "negative-weight single company": BinaryOption(legs=(OptionLeg(2, -1.0),), option_id=3,
                                                    steps_until_expiry=3, strike=-1000.0),
    "steps=0 (already expired)": BinaryOption(legs=(OptionLeg(2, 1.0),), option_id=4,
                                              steps_until_expiry=0, strike=1000.0),
    "steps=200 (very long)": BinaryOption(legs=(OptionLeg(2, 1.0),), option_id=5,
                                          steps_until_expiry=200, strike=1000.0),
    "strike=0 single leg": BinaryOption(legs=(OptionLeg(2, 1.0),), option_id=6,
                                        steps_until_expiry=3, strike=0.0),
    "strike huge": BinaryOption(legs=(OptionLeg(2, 1.0),), option_id=7,
                                steps_until_expiry=3, strike=1e15),
    "spread same-sign weights (out of spec)": BinaryOption(
        legs=(OptionLeg(2, 1.0), OptionLeg(3, 1.0)), option_id=8, steps_until_expiry=3, strike=1500.0),
    "spread nonzero strike (out of spec)": BinaryOption(
        legs=(OptionLeg(2, 1.0), OptionLeg(3, -1.0)), option_id=9, steps_until_expiry=3, strike=50.0),
    "three legs (out of spec)": BinaryOption(
        legs=(OptionLeg(1, 1.0), OptionLeg(2, 1.0), OptionLeg(3, -1.0)), option_id=10,
        steps_until_expiry=3, strike=500.0),
    "FED + company mixed weight sign": BinaryOption(
        legs=(OptionLeg(1, -1.0), OptionLeg(2, 1.0)), option_id=11, steps_until_expiry=3, strike=998.0),
}
for label, opt in OPT_CASES.items():
    def fn(o=opt):
        mm = MarketMaker(unds_normal, [o], 20.0)
        model = mm._estimate(MarketHistory(values_by_underlying_id=HIST_CASES["60 days realistic"]))
        assert model is not None
        values = mm._values()
        p = _price(model, o, values)              # UNWRAPPED pricer
        assert 0.0 <= p <= 1.0, f"price out of [0,1]: {p}"
        sig = _sigma_eps(model, o, values)         # UNWRAPPED sigma
        assert sig >= 0.0 and not math.isnan(sig)
        mm._model = model
        q = mm.quote(o, 42)                        # policy layer -- keep wrapped (it's meant to degrade)
        assert 0.0 <= q.bid_price < q.offer_price <= 1.0
        f = FokOrder(counterparty_id=1, option_id=o.option_id, order_type=OrderType.BUY,
                    price=0.5, quantity=1)
        mm.respond_to_fok(o, f)
    probe(f"option shape: {label}", fn)

# ---- underlying-state edge cases ----
UND_CASES = {
    "FED = 0.0 exactly": [Underlying("FED", 1, 0.0), Underlying("AJR", 2, 1000.0), Underlying("THR", 3, 750.0)],
    "AJR = 0.0 exactly": [Underlying("FED", 1, 2.0), Underlying("AJR", 2, 0.0), Underlying("THR", 3, 750.0)],
    "both companies = 0.0": [Underlying("FED", 1, 2.0), Underlying("AJR", 2, 0.0), Underlying("THR", 3, 0.0)],
    "FED off-grid (e.g. 2.13)": [Underlying("FED", 1, 2.13), Underlying("AJR", 2, 1000.0), Underlying("THR", 3, 750.0)],
    "FED very high (10.0)": [Underlying("FED", 1, 10.0), Underlying("AJR", 2, 1000.0), Underlying("THR", 3, 750.0)],
    "extreme AJR/THR ratio": [Underlying("FED", 1, 2.0), Underlying("AJR", 2, 1e-6), Underlying("THR", 3, 1e6)],
}
opt_std = BinaryOption(legs=(OptionLeg(2, 1.0), OptionLeg(3, -1.0)), option_id=99, steps_until_expiry=3, strike=0.0)
for label, unds in UND_CASES.items():
    def fn(u=unds):
        mm = MarketMaker(u, [opt_std], 20.0)
        model = mm._estimate(MarketHistory(values_by_underlying_id=HIST_CASES["60 days realistic"]))
        assert model is not None
        values = {x.underlying_id: x.value for x in u}
        p = _price(model, opt_std, values)         # UNWRAPPED pricer
        assert 0.0 <= p <= 1.0, f"price out of [0,1]: {p}"
        mm._model = model
        q = mm.quote(opt_std, 7)
    probe(f"underlying state: {label}", fn)

# ---- cash / callback edge cases ----
def cash_case_1():
    mm = MarketMaker(unds_normal, [opt_std], 0.01)
    mm.quote(opt_std, 1)


def cash_case_2():
    mm = MarketMaker(unds_normal, [opt_std], 0.0)
    mm.quote(opt_std, 1)


def cash_case_3():
    mm = MarketMaker(unds_normal, [opt_std], 20.0)
    for _ in range(50):
        mm.on_trade(opt_std, 0.5, 20, 55)
    mm.quote(opt_std, 55)


def cash_case_4():
    mm = MarketMaker(unds_normal, [opt_std], 20.0)
    mm.on_step_advance(unds_normal, [])   # zero active options


probe("cash=0.01", cash_case_1)
probe("cash=0.0", cash_case_2)
probe("deeply over-locked before quoting again", cash_case_3)
probe("on_step_advance with zero options", cash_case_4)

print(f"probes run: {len(HIST_CASES) + len(OPT_CASES) + len(UND_CASES) + 4}")
if fails:
    print(f"\n{len(fails)} SILENT-EXCEPTION CANDIDATES FOUND:\n")
    for label, tb in fails:
        print(f"--- {label} ---\n{tb}\n")
else:
    print("NONE FOUND: every probed input reaches the real logic without raising.")
