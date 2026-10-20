"""Benchmark our per-test PnL against another participant's published table.

Their "hidden test k" should map to our TC(k+4) -- the 16 SCORED tests. Verify via
starting capital and opponent roster before trusting any of it. Their numbers are
transcribed from a screenshot: treat as UNVERIFIED, but the capital/roster match is
a strong integrity check.
"""
import os
import re

# transcribed from the shared screenshot (participant "Shao-lyn-D10R")
THEIRS = [
    # (hidden#, start capital, their PnL, rank, N, score, leader)
    (1, 10, 1.60, 2, 2, 0.40, "Stalemate Quoter 39.00"),
    (2, 10, -4.70, 3, 3, 0.40, "Fixed Width 0.25 14.94"),
    (3, 10, -0.82, 2, 3, 0.40, "Fixed Width 0.25 25.93"),
    (4, 10, 9.71, 2, 3, 0.70, "Fixed Width 0.10 23.63"),
    (5, 10, 23.41, 1, 3, 1.00, "THEM"),
    (6, 20, 15.98, 2, 3, 0.70, "Fixed Width 0.10 30.60"),
    (7, 20, 20.19, 1, 3, 1.00, "THEM"),
    (8, 20, 2.33, 1, 2, 1.00, "THEM"),
    (9, 20, 20.54, 1, 4, 1.00, "THEM"),
    (10, 20, 10.07, 2, 3, 0.70, "Lattice 26.57"),
    (11, 20, 31.37, 1, 3, 1.00, "THEM"),
    (12, 40, 37.15, 1, 4, 1.00, "THEM"),
    (13, 40, 48.86, 1, 4, 1.00, "THEM"),
    (14, 40, 20.58, 2, 4, 0.80, "Fixed Width 0.05 36.09"),
    (15, 40, -3.32, 2, 4, 0.80, "Situational Unawareness 22.93"),
    (16, 40, -5.66, 1, 4, 1.00, "THEM (negative PnL still won)"),
]

txt = open(os.path.join(os.path.dirname(__file__), "Compiler_Messages_Run_11.txt"),
           encoding="utf-8", errors="ignore").read()
blocks = re.split(r"Test Case (\d+):", txt)[1:]
ours = {}
for tc, body in zip(map(int, blocks[0::2]), blocks[1::2]):
    rank = re.findall(r"\d+\.\s+(.+?):\s+\$(-?[0-9.]+)", body)
    cap = re.search(r"starting capital:\s*([0-9.]+)", body)
    sc = re.search(r"score=([0-9.]+)", body)
    if rank and cap:
        ours[tc] = {"pnl": dict(rank).get("Hamza Khan"), "cap": float(cap.group(1)),
                    "n": len(rank), "score": float(sc.group(1)) if sc else None,
                    "rank": [n for n, _ in rank].index("Hamza Khan") + 1,
                    "board": rank}

print("=== integrity check: does hidden#k == our TC(k+4)? ===")
ok = True
for h, cap, *_ in THEIRS:
    tc = h + 4
    match = ours[tc]["cap"] == cap
    ok &= match
    print(f"  hidden {h:>2} -> TC{tc:<3} capital ${cap:<5.0f} vs ours ${ours[tc]['cap']:<5.0f}  "
          f"{'match' if match else 'MISMATCH'}")
print(f"  => {'MAPPING CONFIRMED on all 16 capitals' if ok else 'MAPPING BROKEN'}\n")

print("=== per-test benchmark (our Run 11/13 vs theirs) ===")
print(f"{'TC':>4}{'cap':>5}{'our PnL':>10}{'their PnL':>11}{'ours':>7}{'theirs':>8}   verdict")
gap = 0.0
for h, cap, tpnl, trank, tn, tscore, leader in THEIRS:
    tc = h + 4
    o = ours[tc]
    opnl = float(o["pnl"])
    oscore = 0.8 if tc == 18 else o["score"]        # TC18 improved to 0.8 in Run 13
    d = tscore - oscore
    gap += max(d, 0)
    verdict = ("THEY WIN +%.1f" % d if d > 0 else
               ("we win +%.1f" % -d if d < 0 else "tie"))
    print(f"{tc:>4}{cap:>5.0f}{opnl:>10.2f}{tpnl:>11.2f}{oscore:>7.2f}{tscore:>8.2f}   {verdict}")

our_tot = sum(0.8 if tc == 18 else ours[tc]["score"] for tc in range(5, 21)) + 4.0
their_tot = sum(t[5] for t in THEIRS) + 4.0
print(f"\n  our total {our_tot:.1f}   their total {their_tot:.1f}")
print(f"  points they take that we don't: {gap:.1f}")
print("\n=== where they prove a test is winnable that we lose ===")
for h, cap, tpnl, trank, tn, tscore, leader in THEIRS:
    tc = h + 4
    oscore = 0.8 if tc == 18 else ours[tc]["score"]
    if tscore > oscore:
        print(f"  TC{tc}: they {tpnl:+.2f} (score {tscore:.2f}) vs us {float(ours[tc]['pnl']):+.2f} "
              f"(score {oscore:.2f})  swing ${tpnl - float(ours[tc]['pnl']):+.2f}")
        print(f"        our board was: {', '.join(f'{n} {v}' for n, v in ours[tc]['board'])}")
