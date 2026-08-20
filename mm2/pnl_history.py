"""Full PnL history (not just score) for every participant in every 'never-won' test,
across all 8 runs. If our PnL barely moves despite completely different code across
runs, that's a mechanical/engagement problem, not a structural ceiling.
"""
import glob
import re

NEVER_WON = [5, 6, 8, 10, 18, 19]

files = sorted(glob.glob("**/Compiler_Messages_Run_*.txt", recursive=True),
               key=lambda p: int(re.search(r"Run_(\d+)", p).group(1)))

data = {}  # tc -> run -> {name: pnl}
for path in files:
    run = re.search(r"Run_(\d+)", path).group(1)
    txt = open(path, encoding="utf-8", errors="ignore").read()
    blocks = re.split(r"Test Case (\d+):", txt)[1:]
    for tc, body in zip(map(int, blocks[0::2]), blocks[1::2]):
        if tc not in NEVER_WON:
            continue
        board = dict(re.findall(r"\d+\.\s+(.+?):\s+\$(-?[0-9.]+)", body))
        data.setdefault(tc, {})[run] = board

runs = [re.search(r"Run_(\d+)", p).group(1) for p in files]
for tc in NEVER_WON:
    print(f"=== TC{tc} ===")
    names = sorted({n for r in data[tc].values() for n in r})
    header = f"{'participant':>26}" + "".join(f"{'R' + r:>9}" for r in runs)
    print(header)
    for name in names:
        row = f"{name:>26}"
        for r in runs:
            v = data[tc].get(r, {}).get(name)
            row += f"{v:>9}" if v is not None else f"{'--':>9}"
        print(row)
    us = [data[tc][r].get("Hamza Khan") for r in runs if "Hamza Khan" in data[tc].get(r, {})]
    us_f = [float(x) for x in us]
    print(f"  our PnL range: [{min(us_f):.2f}, {max(us_f):.2f}]  spread={max(us_f)-min(us_f):.2f}")
    print()
