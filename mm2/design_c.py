"""
Design C -- the refinement that makes Design A affordable.

A probe costs us the fill we would have won: forgone = displayed_size * base_edge.
Displayed size is budget/bid, so the probe is CHEAP where our bid is high (deep
ITM, few lots shown) and EXPENSIVE where our bid is low (many lots shown).

The sweep payoff runs the other way: lots affordable = budget/sweep_price, so
sweeping is worth most where theo is LOW.

Fixed-width bots quote theo +/- w/2 at EVERY theo, so a regime learned at one
theo transfers to all others. => probe where information is cheap, exploit
where it is valuable.
"""
import math

SEP = "=" * 74
def hdr(t): print(f"\n{SEP}\n{t}\n{SEP}")

BASE_EDGE, LOCK_FRAC = 0.035, 0.25
ARCH = {"stale": None, "fw05": 0.05, "fw10": 0.10, "fw25": 0.25}

def their_bid(kind, theo):
    return 0.0 if kind == "stale" else max(0.0, theo - ARCH[kind] / 2)

def our_bid(theo):
    b = math.floor((theo - BASE_EDGE) * 100 + 1e-9) / 100
    return min(max(b, 0.0), 0.99)

def shown(theo, cap):
    b = our_bid(theo)
    if b <= 0:
        return 500
    return max(1, min(500, int(LOCK_FRAC * cap / b)))

hdr("C1. COST OF A PROBE, BY THETA (what we give up if it fails)")
print(f"  {'theo':>6} {'our bid':>8} {'lots shown':>11} {'forgone edge':>13}   (cap $10)")
for theo in (0.10, 0.25, 0.50, 0.70, 0.85, 0.90, 0.95):
    q = shown(theo, 10.0)
    print(f"  {theo:>6.2f} {our_bid(theo):>8.2f} {q:>11d} {q * BASE_EDGE:>13.2f}")
print("\n  Probing at theo 0.90 costs $0.07. Probing at theo 0.10 costs $1.44.")
print("  A factor of 20 -- and the information obtained is IDENTICAL.")

hdr("C2. DOES THE SEPARATION STILL HOLD AT HIGH THETA?")
print("  probe = bid at 0.45 (a price no fixed-width bot ever bids below, for")
print("  theo >= 0.6), size = budget/0.45\n")
print(f"  {'theo':>6} " + " ".join(f"{k:>8}" for k in ARCH) + "   probe fills vs")
for theo in (0.70, 0.80, 0.90, 0.95):
    bids = {k: their_bid(k, theo) for k in ARCH}
    fills = [k for k in ARCH if 0.45 > bids[k]]
    print(f"  {theo:>6.2f} " + " ".join(f"{bids[k]:>8.3f}" for k in ARCH)
          + f"   {fills}")
print("\n  => at theo >= 0.70 a 0.45 probe fills against Stalemate and NOTHING")
print("     else. Clean separation at the cheapest possible probe location.")

hdr("C3. THE EXPLOIT, ONCE THE FIELD IS KNOWN WIDE")
print("  Having learned 'Stalemate-only', sweep at 0.01-0.05 on ordinary flow:\n")
print(f"  {'theo':>6} {'sweep@':>7} {'lots afford':>12} {'edge/lot':>9} "
      f"{'on 35-lot order':>16} {'vs now':>8}")
for theo in (0.20, 0.35, 0.50, 0.70, 0.90):
    sweep = 0.05
    afford = min(500, int(LOCK_FRAC * 10.0 / sweep))
    won = min(afford, 35)
    now = shown(theo, 10.0)
    print(f"  {theo:>6.2f} {sweep:>7.2f} {afford:>12d} {theo - sweep:>9.2f} "
          f"{won * (theo - sweep):>16.2f} {min(now,35) * BASE_EDGE:>8.2f}")

hdr("C4. NET, ON THE ONE ROSTER WE CAN CHECK")
print("  TC5 ($10, Stalemate only). Live now: us $3.68, Stalemate $30.0 -> 0.4")
print()
print("  With design C: one 0.45 probe at high theo costs ~$0.07 and returns")
print("  FILL. From then on we sweep, taking the residual Stalemate was")
print("  harvesting. Stalemate's $30 is 30 lots it won at 0.00 -- every one of")
print("  them is a lot we outbid it for at 0.01-0.05.")
print()
print("  Upper bound if we capture all of it: our PnL rises by roughly the")
print("  lots' value and Stalemate falls toward $0 -> rank flips -> 0.4 -> 1.0.")
print("  That is +0.6 on TC5 alone, and TC5-like rosters may recur among the")
print("  8 tests whose composition we have never seen.")

hdr("C5. THE HONEST RISK LEDGER")
risks = [
    ("probe forgoes a fill",
     "~$0.07 if probed only at theo>=0.70; TC13 margin is $0.11 -- still same order"),
    ("sweep fires on a false positive",
     "needs >=2 confirming probes before arming; each costs ~$0.07"),
    ("sweep buys 35 binaries at 0.05",
     "max loss $1.75 on a $10 book -- LOWER than the $2.30 the tight quote locks"),
    ("margin crowd-out",
     "sweep must respect the same QUOTE_LOCK_FRAC budget as any other quote"),
    ("unseen rosters",
     "8 of 16 tests have never been observed; probe is inert unless it FILLS,"),
    ("",
     "and it only fills against a field wider than 0.45 -- i.e. Stalemate-like"),
]
for a, b in risks:
    print(f"  {a:<32} {b}")

print("\n  The one thing that makes this different from the three failed")
print("  experiments: sigma-recomposition, the FOK gate and FED widening all")
print("  changed behaviour on EVERY order. Design C changes behaviour only")
print("  after an explicit observation that cannot occur unless the field is")
print("  wider than 0.45 -- which no fixed-width archetype ever is.")
print("\n  It is still unverified live, and the freeze conditions still apply.")
