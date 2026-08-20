"""
Two candidate designs, evaluated deterministically (no Monte-Carlo, no arena).

The arena is not trusted (it inverts the one ranking we can check, MEMORY E53/E55).
But "who wins an auction" is not a simulation question -- fixed-width bots quote a
DETERMINISTIC function of theo, so the winner is arithmetic. That is all we use.

Design A: PROBE. Occasionally bid far from theo to learn the best competing bid,
          then exploit if the field turns out to be wide.
Design B: PENNY-INSIDE. Where we already quote the free-roll 0.00/1.00 and TIE
          with Stalemate (50/50 split), quote 0.01/0.99 instead and take 100%
          by price priority. No inference required.
"""
import math

SEP = "=" * 74
def hdr(t): print(f"\n{SEP}\n{t}\n{SEP}")

# competing bid as a function of theo, per archetype (bid side; offer is mirrored)
def bid_of(kind, theo):
    if kind == "stale":
        return 0.00
    w = {"fw05": 0.05, "fw10": 0.10, "fw25": 0.25}[kind]
    return max(0.0, theo - w / 2)

def offer_of(kind, theo):
    if kind == "stale":
        return 1.00
    w = {"fw05": 0.05, "fw10": 0.10, "fw25": 0.25}[kind]
    return min(1.0, theo + w / 2)

KNOWN = {
    "TC5":  (10.0, ["stale"],         0.4),
    "TC6":  (10.0, ["fw25", "stale"], 0.4),
    "TC7":  (10.0, ["fw25"],          1.0),
    "TC8":  (10.0, ["fw10", "stale"], 0.7),
    "TC9":  (10.0, ["fw10", "fw25"],  1.0),
    "TC10": (20.0, ["fw10", "stale"], 0.7),
    "TC11": (20.0, ["fw05", "fw10"],  1.0),
    "TC12": (20.0, ["fw05"],          1.0),
}

# ---------------------------------------------------------------- Design A
hdr("DESIGN A -- PROBE: can a cheap experiment identify the field?")

print("  A probe = bid at theo - d for large d, once, and observe fill / no fill.")
print("  It reveals whether ANY competitor bids above theo - d.\n")
print("  outcome of a probe at depth d, theo 0.50, by roster:")
print(f"    {'test':<6} {'roster':<18} {'best comp bid':>14} " +
      " ".join(f"{f'd={d:.2f}':>8}" for d in (0.10, 0.20, 0.30, 0.45)))
theo = 0.50
for tc, (cap, opps, sc) in KNOWN.items():
    best = max(bid_of(o, theo) for o in opps)
    cells = []
    for d in (0.10, 0.20, 0.30, 0.45):
        cells.append(f"{'FILL' if theo - d > best else 'none':>8}")
    print(f"    {tc:<6} {str(opps):<18} {best:>14.3f} " + " ".join(cells))

print("\n  A probe at d=0.45 (bid 0.05) FILLS only in TC5 -- the one roster where")
print("  sweeping is right. It is a clean separator: exactly the Stalemate-only")
print("  rosters answer FILL, every roster containing a fixed-width bot answers")
print("  'none'. Note TC6 (fw25+stale) correctly answers 'none': FW0.25 bids")
print("  0.375, so sweeping there would be wrong, and the probe says so.\n")

print("  cost of one failed probe (we forgo the fill we would have won):")
budget_frac = 0.25
for tc, (cap, opps, sc) in KNOWN.items():
    best = max(bid_of(o, theo) for o in opps)
    our_normal = 0.46
    if our_normal > best:
        q = max(1, min(500, int(budget_frac * cap / our_normal)))
        forgone = q * (theo - our_normal)
    else:
        forgone = 0.0     # we would not have won anyway -> probe is FREE
    print(f"    {tc:<6} {str(opps):<18} forgone ${forgone:>5.2f}"
          + ("   (probe is free -- we lose this auction regardless)" if forgone == 0 else ""))

print("\n  payoff of a successful probe (TC5, 35-lot order, bid 0.05):")
print(f"    35 lots x $0.45 edge = $15.75, versus $0.20 for the tight quote.")
print("    reward:risk ~ 79:1.")

print("\n  BUT -- the cost is not zero where it matters. TC13 is held by $0.11")
print("  (MEMORY E47). A single forgone $0.20 fill flips it. Probing is only")
print("  safe if the probe is skipped once we are provably ahead, which needs")
print("  the rank we cannot observe. This is the same circularity as PROBLEM 5.")

# ---------------------------------------------------------------- Design B
hdr("DESIGN B -- PENNY-INSIDE: beat the tie, no inference needed")

print("  Where does our free-roll actually fire? offer >= 1.00 requires")
print("  theo + width >= 0.995, i.e. theo >= ~0.96. Symmetrically bid <= 0.00")
print("  requires theo <= ~0.04. So free-roll fires ONLY on extreme-theo options,")
print("  and there we quote exactly 0.00/1.00 -- the same price as Stalemate.\n")

print("  Current: we TIE at 1.00 -> equal split, size-invariant (MEMORY E35).")
print("  With one competitor at the same price we receive HALF the order.")
print("  At 0.99 we have price priority and receive ALL of it.\n")

print(f"    {'theo':>6} {'our offer':>10} {'edge/lot':>9} {'lock/lot':>9} "
      f"{'share now':>10} {'share @0.99':>12}")
for theo_x in (0.960, 0.970, 0.980, 0.985, 0.990, 0.995):
    edge99 = 0.99 - theo_x
    print(f"    {theo_x:>6.3f} {1.00:>10.2f} {1.00 - theo_x:>9.3f} {0.00:>9.2f} "
          f"{'50%':>10} {'100%' if edge99 > 0 else 'SKIP (neg edge)':>12}")

print("\n  The rule writes itself and needs no regime inference:")
print("    if our computed offer rounds to 1.00 AND theo <= 0.99 - floor:")
print("        offer 0.99, size = budget / 0.01   (capped)")
print("    else keep 1.00 (zero-lock free roll)")
print("  Mirrored on the bid: 0.01 when theo >= 0.01 + floor.\n")

print("  Properties that matter given our track record:")
print("    * it is STRUCTURAL (fixes a tie into a win), the only family that has")
print("      ever gained live: capacity fix +1.6, free-roll +0.5.")
print("    * it is INERT wherever free-roll does not already fire, i.e. on all")
print("      normal-theo flow -- so it cannot disturb the 9 tests we win on")
print("      ordinary quoting.")
print("    * it never quotes negative edge (the theo <= 0.99 - floor guard).")
print("    * BUT it converts a zero-margin quote into a 1c/lot margin quote.")
print("      At 500 lots that is $5 on a $10 book. It MUST be budget-sized, or")
print("      it will crowd out ordinary quoting and could threaten solvency.")

hdr("COMPARISON")
rows = [
    ("A  probe",        "yes, active", "TC5-like only", "forgoes fills; TC13 held by $0.11", "NO"),
    ("B  penny-inside", "none needed", "extreme-theo flow", "consumes margin; needs sizing", "MAYBE"),
]
print(f"  {'design':<16} {'inference':<13} {'where it acts':<20} {'main risk':<34} {'ship?'}")
for r in rows:
    print(f"  {r[0]:<16} {r[1]:<13} {r[2]:<20} {r[3]:<34} {r[4]}")

print("\n  Design A is the theoretically right answer to 'can we adapt' -- and the")
print("  probe genuinely separates the rosters. It is still not shippable blind,")
print("  because its cost lands precisely on the margin that holds TC13.")
print("  Design B needs no adaptation at all, sits in the one family that has")
print("  ever gained, and is inert outside extreme-theo flow.")
print("\n  Neither is verified live. Both violate the standing freeze unless the")
print("  E46/E47 conditions are met: known deadline, >=3 spare submissions,")
print("  and worst-case-proof inertness on all 9 tests currently won.")
