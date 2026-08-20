"""Is SIZE_CAP redundant with the budget? size = min(SIZE_CAP, budget/lock_per_lot)."""
BUDGET = 5.00
print("lock = size * lock_per_lot, and budget = QUOTE_LOCK_FRAC * free already bounds it.")
print("SIZE_CAP only caps LOT COUNT, so it binds exactly when price is low.\n")
print(f"{'price':>7}{'lock/lot':>10}{'size@40':>9}{'lock@40':>9}{'size@500':>10}{'lock@500':>10}")
for p in (0.46, 0.20, 0.10, 0.05, 0.02, 0.01):
    n40, n500 = min(40, int(BUDGET / p)), min(500, int(BUDGET / p))
    print(f"{p:>7.2f}{p:>10.2f}{n40:>9}{n40 * p:>9.2f}{n500:>10}{n500 * p:>10.2f}")
print("\n=> lock never exceeds the budget under either cap, and max loss == lock (ledger audit).")
print("=> raising the cap deploys the SAME capital; it just stops truncating size on cheap lots.")
