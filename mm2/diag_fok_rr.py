"""The three FOKs we accepted in TC4 VERBOSE, and what a risk-reward gate does to them.

TC4 is the only test where we can watch ourselves lose money trade by trade:
all three accepted FOKs were "customer buys an ITM option off us above our theo",
and all three expired ITM. Total -$5.32.
"""
# (label, side we take, price, theo, qty, realised payoff)
TRADES = [
    ("sell 26 @ 0.94 (1d THR>=624)", "sell", 0.94, 0.8184, 26, 1.0),
    ("sell  2 @ 0.99 (1d THR>=624)", "sell", 0.99, 0.8184, 2, 1.0),
    ("sell 17 @ 0.78 (1d AJR>=1315)", "sell", 0.78, 0.7337, 17, 1.0),
    # a junk trade of the kind we must NOT block, for contrast
    ("buy  25 @ 0.01 (junk, theo .07)", "buy", 0.01, 0.07, 25, 0.0),
]

for k in (1.0, 2.0, 3.0):
    print(f"--- FOK_RISK_REWARD = {k} (accept iff expected loss <= k * edge) ---")
    print(f"{'trade':>34}{'edge':>7}{'E[loss]':>9}{'ratio':>7}{'realised':>10}   verdict")
    kept = 0.0
    for label, side, c, p, q, payoff in TRADES:
        if side == "sell":
            edge, loss_per, p_loss = c - p, 1.0 - c, p
            realised = q * (c - payoff)
        else:
            edge, loss_per, p_loss = p - c, c, 1.0 - p
            realised = q * (payoff - c)
        eloss = p_loss * loss_per
        ratio = eloss / edge if edge > 0 else float("inf")
        ok = ratio <= k
        kept += realised if ok else 0.0
        print(f"{label:>34}{edge:>7.3f}{eloss:>9.3f}{ratio:>7.2f}{realised:>10.2f}   "
              f"{'accept' if ok else 'REJECT'}")
    print(f"{'':>34}{'':>7}{'':>9}{'':>7}{kept:>10.2f}   <- realised PnL kept\n")
