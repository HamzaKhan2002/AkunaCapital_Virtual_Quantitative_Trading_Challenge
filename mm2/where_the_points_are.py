"""
Where the remaining 2.6 points actually are, and whether the signal needed to
capture them is observable in-session.

Follows PROBLEM.md section 7: compute the information limit BEFORE writing policy.

Facts used (all sourced, none fitted here):
  * Stalemate Quoter quotes 0.00 bid / 1.00 offer in huge size   [GROUND_TRUTH.md L52]
  * RFQ routing = best price wins, residual spills to next level [GROUND_TRUTH.md L22]
  * ties split equally, size-invariant                           [MEMORY.md E35]
  * our config: BASE_EDGE .035, QUOTE_LOCK_FRAC .25, cap 500     [Market_Maker_2.py L354-364]
  * live TC5: Stalemate $30.0, us $3.68                          [Compiler_Messages_Run_12.txt L117]
"""
import math

SEP = "=" * 74


def hdr(t):
    print(f"\n{SEP}\n{t}\n{SEP}")


# ----------------------------------------------------------------- 1. the leak
hdr("1. THE LEAK: what our displayed size actually is")

print("  Stalemate's PnL is an INTEGER in every single log ($43, $30, $5, $2, $0).")
print("  It buys at 0.00 (pays nothing) and sells at 1.00 (receives exactly 1).")
print("  A binary settles 0 or 1 => its PnL is a literal COUNT of free lots won.")
print("  So 'Stalemate: $30.0' in TC5 = 30 lots that spilled past our quote.\n")

print("  our displayed bid size, by capital and theo (UNKNOWN class, util=0):")
print(f"    {'theo':>6} {'bid':>6} {'lock/lot':>9} | " +
      " ".join(f"{f'${c} cap':>9}" for c in (10, 20, 40)))
for theo in (0.10, 0.25, 0.50, 0.75, 0.90):
    bid = math.floor((theo - 0.035) * 100 + 1e-9) / 100
    bid = min(max(bid, 0.0), 0.99)
    row = f"    {theo:>6.2f} {bid:>6.2f} {bid:>9.2f} | "
    cells = []
    for cap in (10, 20, 40):
        budget = 0.25 * cap
        q = 500 if bid <= 0 else max(1, min(500, int(budget / max(bid, 0.01))))
        cells.append(f"{q:>9d}")
    print(row + " ".join(cells))

print("\n  => at theo 0.50 on $10 we show FIVE lots. The flow contains orders of")
print("     12-200 lots. Everything above 5 goes to Stalemate at 0.00, for free.")
print("     This is not a pricing error and not a width error. It is a CAPACITY")
print("     error, and margin is the binding constraint.")

# --------------------------------------------------- 2. why widening is free here
hdr("2. THE KEY ASYMMETRY: on a bid, margin per lot IS the price")

print("  lock/lot = bid price. So a LOWER bid buys MORE lots with the SAME margin,")
print("  and each lot carries MORE edge. Both move the right way at once.\n")
budget, theo = 2.50, 0.50
print(f"  $10 capital, budget ${budget:.2f}, theo {theo:.2f}, a 35-lot customer sell:\n")
print(f"    {'our bid':>8} {'lots afford':>12} {'lots won':>9} {'edge/lot':>9} "
      f"{'E[profit]':>10} {'worst case':>11}")
for bid in (0.46, 0.40, 0.30, 0.20, 0.10, 0.05, 0.01):
    afford = min(500, int(budget / bid))
    won = min(afford, 35)
    edge = theo - bid
    print(f"    {bid:>8.2f} {afford:>12d} {won:>9d} {edge:>9.2f} "
          f"{won * edge:>10.2f} {-won * bid:>11.2f}")

print("\n  Bidding 0.05 instead of 0.46 wins 35 lots instead of 5, earns $15.75")
print("  instead of $0.18, and RISKS LESS ($1.75 vs $2.30 worst case).")
print("  It is dominant in every dimension -- PROVIDED nobody outbids us.")
print("  That proviso is the entire problem, and it is roster-dependent:")
print("    vs Stalemate (bids 0.00)      -> 0.05 wins the whole order")
print("    vs Fixed Width 0.25 (bids 0.375) -> 0.05 wins nothing, 0.46 wins")
print("  So the correct bid depends on WHO ELSE IS QUOTING -- never observable")
print("  directly. The question is whether it is observable INDIRECTLY.")

# ------------------------------------------------- 3. the regime signal
hdr("3. IS THE COMPETITIVE REGIME OBSERVABLE? (the thin-data question)")

print("  Observable at zero cost, every RFQ we win: our FILL QUANTITY, versus the")
print("  size we DISPLAYED. We know both. Define the capped event")
print("        C = 1[ fill_qty == displayed_qty ]")
print("  C=1 means the order was at least our size AND we were top of book,")
print("  i.e. residual existed and spilled to someone worse-priced.\n")

print("  P(C=1) by regime, at theo 0.50, $10 capital (we display 5):")
regimes = [
    ("Stalemate only",        0.00, "we are always top of book"),
    ("Fixed Width 0.25",      0.375, "we outbid it, still capped"),
    ("Fixed Width 0.10",      0.45, "we outbid it, still capped"),
    ("Fixed Width 0.05",      0.475, "it outbids us -> no fill at all"),
]
our_bid = 0.46
for nm, their_bid, note in regimes:
    win = our_bid > their_bid
    print(f"    {nm:<20} their bid {their_bid:>5.3f}  we {'WIN ' if win else 'LOSE'}"
          f"   P(C=1) ~ {1.0 if win else 0.0:>3.1f}   ({note})")

print("\n  The signal is very nearly DETERMINISTIC, not statistical: fixed-width")
print("  bots quote a fixed function of theo, so 'do we outbid them' is the same")
print("  answer every time. Contrast the PnL channel, where the same question")
print("  needed 183-965 settled trades.\n")

for p_alt in (0.9, 0.75, 0.6):
    # trials until a Bernoulli(1.0) vs Bernoulli(p_alt) separation is unambiguous
    n = math.ceil(math.log(0.05) / math.log(p_alt)) if p_alt < 1 else 0
    print(f"    to reject 'regime is p={p_alt}' after seeing ALL-capped: {n} RFQs "
          f"(we get ~22)")

print("\n  => The regime is identifiable in a handful of orders. The thin-data")
print("     objection is REAL for PnL and FALSE for the competitive regime.")

# ------------------------------------------------- 4. what it is worth
hdr("4. WHAT IT IS WORTH, AND WHAT IT RISKS")

print("  Tests where Stalemate is present are exactly the tests we do not win:")
tests = [("TC5", 10, ["stale"], 0.4, "Stalemate $30.0 vs us $3.68"),
         ("TC6", 10, ["fw25", "stale"], 0.4, "FW25 $11.94, Stale $0.0, us -$4.82"),
         ("TC8", 10, ["fw10", "stale"], 0.7, "FW10 $23.46, us $10.51, Stale $0.0"),
         ("TC10", 20, ["fw10", "stale"], 0.7, "FW10 $29.87, us $17.61, Stale $0.0")]
for tc, cap, opp, sc, note in tests:
    print(f"    {tc:<5} ${cap:<3} {str(opp):<18} scored {sc}   {note}")
print("    TC7/TC9/TC11/TC12 (no Stalemate) ................ scored 1.0 each")

print("\n  Note TC8/TC10: we ALREADY starved Stalemate to $0.00 there (capacity fix)")
print("  and still lost to the fixed-width bot. So the residual-sweep idea only")
print("  clearly addresses TC5, and TC6 is a loss to FW0.25, not to Stalemate.")
print("  Honest upper bound on this idea: TC5 0.4->1.0, i.e. +0.6, plus whatever")
print("  it does in the 8 unseen rosters. NOT the whole 2.6-point gap.\n")

print("  The risk is precise and must be stated: bidding wide when a tighter bot")
print("  is present forfeits flow we currently win. TC7 is won by outbidding")
print("  FW0.25 at 0.46 vs 0.375. A wide bid there loses a test we hold.")
print("  Any policy MUST therefore be gated on the capped-signal and must be")
print("  provably inert when we are not capped.")

hdr("VERDICT")
print("  Adaptive is possible. The user's worry -- data too thin -- is correct for")
print("  every channel we previously tried and wrong for this one:")
print()
print("    channel               obs/session   noise            usable?")
print("    realised PnL          ~15           Bernoulli, huge  NO  (short 12-64x)")
print("    observed order price  ~22           none             YES (+/- 2c)")
print("    fill vs displayed     ~22           none, ~binary    YES (a few obs)")
print()
print("  The last one is new, is the strongest of the three, and points straight")
print("  at the one leak we can still name: residual size donated at 0.00/1.00.")
