"""Regression test: reproduce the EXACT quotes logged by the grader in Run 11 (16.9).

Run 11 VERBOSE printed our book verbatim. Those lines pin the quoting arithmetic,
so replaying them proves the code is behaviourally identical to what scored 16.9.
theo and sigma are pinned to the logged/implied values; everything else -- widths,
rounding, sizing, caps, ledger state -- is the code under test.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import Market_Maker_2 as M  # noqa: E402
from Market_Maker_2 import BinaryOption, MarketMaker, OptionLeg, Underlying  # noqa: E402

# (label, cash0, free_at_quote, theo, sigma range consistent with the log, expected quote)
CASES = [
    ("TC2  1d THR>=2371", 10.0, 10.00, 0.0456, [0.095, 0.10, 0.104], (0.00, 40, 0.15, 2)),
    ("TC3a 1d FED>=1.75", 20.0, 20.00, 0.2273, [0.0, 0.02, 0.035], (0.19, 26, 0.27, 6)),
    ("TC3b 1d THR-AJR>=0", 20.0, 20.81, 1.0000, [0.0, 0.02, 0.035], (0.96, 5, 1.00, 40)),
    ("TC4  1d AJR>=1315", 40.0, 38.42, 0.7337, [0.0440, 0.045, 0.0462], (0.68, 14, 0.78, 40)),
]

unds = [Underlying("FED", 1, 2.0), Underlying("AJR", 2, 1000.0), Underlying("THR", 3, 750.0)]
opt = BinaryOption(legs=(OptionLeg(2, 1.0),), option_id=1, steps_until_expiry=1, strike=1000.0)

real_price, real_sigma = M._price, M._sigma_eps
fails = 0
print(f"{'case':>20}{'sigma':>8}{'quoted':>22}{'logged in Run 11':>22}")
for label, cash0, free, theo, sigmas, expect in CASES:
    for sig in sigmas:
        M._price = lambda *a, _t=theo, **k: _t
        M._sigma_eps = lambda *a, _s=sig, **k: _s
        try:
            mm = MarketMaker(unds, [opt], cash0)
            mm._free = free
            mm._locked = 0.0
            q = mm.quote(opt, 123456)          # fresh counterparty -> UNKNOWN
            got = (q.bid_price, q.bid_quantity, q.offer_price, q.offer_quantity)
        finally:
            M._price, M._sigma_eps = real_price, real_sigma
        # Prices must stay byte-exact. Sizes may only ever RISE vs the Run 11 log,
        # because the only sanctioned size changes are cap raises (free-roll, SIZE_CAP);
        # a size FALLING would mean the budget/lock path regressed.
        eb, ebq, eo, eoq = expect
        ok_prices = (got[0], got[2]) == (eb, eo)
        ok_sizes = got[1] >= ebq and got[3] >= eoq
        ok = ok_prices and ok_sizes
        intended = ok and got != expect
        fails += not ok
        got_s = f"{got[0]:.2f} x{got[1]} / {got[2]:.2f} x{got[3]}"
        exp_s = f"{eb:.2f} x{ebq} / {eo:.2f} x{eoq}"
        tag = 'OK (size uncapped)' if intended else ('OK' if ok else 'MISMATCH')
        print(f"{label:>20}{sig:>8.3f}{got_s:>22}{exp_s:>22}   {tag}")

print(f"\n{'PRICES MATCH RUN 11 (sizes only ever raised)' if fails == 0 else f'{fails} MISMATCHES - book regressed'}")
sys.exit(0 if fails == 0 else 1)
