"""What is actually left? Headroom by test, with the peer benchmark as an existence proof."""
import os
import re

txt = open(os.path.join(os.path.dirname(__file__), "Compiler_Messages_Run_12.txt"),
           encoding="utf-8", errors="ignore").read()
blocks = re.split(r"Test Case (\d+):", txt)[1:]
PEER = {5: 0.40, 6: 0.40, 7: 0.40, 8: 0.70, 9: 1.00, 10: 0.70, 11: 1.00, 12: 1.00,
        13: 1.00, 14: 0.70, 15: 1.00, 16: 1.00, 17: 1.00, 18: 0.80, 19: 0.80, 20: 1.00}

rows = []
for tc, body in zip(map(int, blocks[0::2]), blocks[1::2]):
    if tc < 5:
        continue
    sc = float(re.search(r"score=([0-9.]+)", body).group(1))
    board = re.findall(r"\d+\.\s+(.+?):\s+\$(-?[0-9.]+)", body)
    us = float(dict(board)["Hamza Khan"])
    leader = max(board, key=lambda kv: float(kv[1]))
    rows.append((tc, sc, us, leader, PEER[tc]))

print(f"{'TC':>4}{'ours':>6}{'peer':>6}{'our PnL':>10}{'leader':>34}   status")
proven = capped = 0.0
for tc, sc, us, (ln, lv), pr in rows:
    if sc >= 1.0:
        status = "maxed"
    elif pr > sc:
        status = f"PEER PROVES +{pr - sc:.1f} AVAILABLE"
        proven += pr - sc
    else:
        status = "peer scores <= us: no proof it is winnable"
        capped += 1.0 - sc
    print(f"{tc:>4}{sc:>6.2f}{pr:>6.2f}{us:>10.2f}{ln + ' $' + lv:>34}   {status}")

tot = sum(r[1] for r in rows) + 4.0
print(f"\n  our total {tot:.1f}   (11 tests already at 1.00)")
print(f"  headroom with an EXISTENCE PROOF : {proven:.1f}  -> {tot + proven:.1f}")
print(f"  headroom with NO evidence anyone achieves it: {capped:.1f}")
