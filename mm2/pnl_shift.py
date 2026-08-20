"""Run 10 -> Run 11 PnL shift, ours vs each opponent. Tests the spillover mechanism."""
import re

def load(path):
    txt = open(path, encoding="utf-8", errors="ignore").read()
    blocks = re.split(r"Test Case (\d+):", txt)[1:]
    out = {}
    for tc, body in zip(map(int, blocks[0::2]), blocks[1::2]):
        out[tc] = {n.strip(): float(v) for n, v in
                   re.findall(r"\d+\.\s+(.+?):\s+\$(-?[0-9.]+)", body)}
    return out

a = load(r"mm2\Compiler_Messages_Run_10.txt")
b = load(r"mm2\Compiler_Messages_Run_11.txt")

print(f"{'TC':>4}{'ours R10':>10}{'ours R11':>10}{'delta':>9}   opponents (R10 -> R11)")
tot_us = tot_opp = 0.0
for tc in sorted(set(a) & set(b)):
    if tc < 5:
        continue
    ua, ub = a[tc].get("Hamza Khan", 0.0), b[tc].get("Hamza Khan", 0.0)
    tot_us += ub - ua
    opp = []
    for name in sorted(set(a[tc]) | set(b[tc])):
        if name == "Hamza Khan":
            continue
        oa, ob = a[tc].get(name, 0.0), b[tc].get(name, 0.0)
        tot_opp += ob - oa
        opp.append(f"{name} {oa:+.1f}->{ob:+.1f} ({ob - oa:+.1f})")
    print(f"{tc:>4}{ua:>10.2f}{ub:>10.2f}{ub - ua:>+9.2f}   " + " | ".join(opp))

print(f"\nTOTAL our PnL change:      {tot_us:+.2f}")
print(f"TOTAL opponent PnL change: {tot_opp:+.2f}")
print("spillover hypothesis predicts opponents lose roughly what we gain")
