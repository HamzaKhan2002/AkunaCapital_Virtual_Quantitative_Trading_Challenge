"""Where can we still out-price FW0.1, and does SIZE_CAP bind exactly there?

FW0.1 quotes theo +/- 0.05 flat. Our half-width is
    max(BASE_EDGE, sigma) + CAPITAL_WIDEN * utilization * lock_per_lot
The sigma floor is non-negotiable (narrowing it lost 1.4 pts live, E40), so ATM
we structurally cannot beat 0.05. But sigma is small on DEEP options, where
BASE_EDGE (3.5c) binds instead -- there we DO beat them. Question: is that also
exactly where SIZE_CAP=40 truncates our size?
"""
BASE_EDGE = 0.035
FW01 = 0.05

print("sigma by moneyness measured in-domain (map_sigma.py): deep ~0.029, company ATM ~0.089\n")
print(f"{'theo':>6}{'sigma':>8}{'our width':>11}{'FW0.1':>8}   who wins the price")
for theo, sigma in ((0.50, 0.089), (0.30, 0.070), (0.15, 0.045), (0.08, 0.032),
                    (0.04, 0.029), (0.02, 0.020)):
    w = max(BASE_EDGE, sigma)
    who = "US" if w < FW01 else "FW0.1"
    print(f"{theo:>6.2f}{sigma:>8.3f}{w:>11.3f}{FW01:>8.2f}   {who}")

print("\nnow: at those same prices, does SIZE_CAP=40 truncate us? (budget = 25% of free)")
print(f"{'book':>6}{'budget':>8}{'bid':>7}{'uncapped lots':>15}{'capped@40':>11}{'capital used':>14}")
for cash in (10.0, 20.0, 40.0):
    budget = 0.25 * cash
    for bid in (0.04, 0.02):
        raw = int(budget / bid)
        capped = min(40, raw)
        print(f"{cash:>6.0f}{budget:>8.2f}{bid:>7.2f}{raw:>15}{capped:>11}"
              f"{capped * bid:>10.2f} / {budget:.2f}")

print("\n=> the tests we lose (TC8/TC10/TC18) are the big-flow ones, and the only")
print("   prices where we out-quote FW0.1 are the deep ones -- which is precisely")
print("   where the 40-lot cap leaves most of the budget unused.")
