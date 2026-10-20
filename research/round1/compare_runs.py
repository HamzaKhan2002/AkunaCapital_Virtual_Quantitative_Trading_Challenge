"""Per-test score matrix across all grader runs. Finds structurally unwinnable tests."""
import glob
import os
import re

files = sorted(glob.glob("**/Compiler_Messages_Run_*.txt", recursive=True),
               key=lambda p: int(re.search(r"Run_(\d+)", p).group(1)))
runs = {}
for path in files:
    with open(path, encoding="utf-8", errors="ignore") as fh:
        scores = [float(m) for m in re.findall(r"score=([0-9.]+)", fh.read())]
    runs[re.search(r"Run_(\d+)", path).group(1)] = scores[-16:]

cols = list(runs)
print("TC   " + "".join(f"{'R' + c:>6}" for c in cols) + "   best")
never = []
for i in range(16):
    vals = [runs[c][i] for c in cols]
    best = max(vals)
    mark = "  <-- NEVER WON" if best < 1.0 else ""
    if best < 1.0:
        never.append(i + 5)
    print(f"TC{i + 5:<3}" + "".join(f"{v:>6.1f}" for v in vals) + f"{best:>7.1f}{mark}")
print()
for c in cols:
    print(f"Run {c}: total={sum(runs[c]) + 4.0:.1f}  ones={sum(1 for v in runs[c] if v >= 1.0)}"
          f"  floors={sum(1 for v in runs[c] if v <= 0.4)}")
print(f"\nNever won: {never}  -> headroom = {sum(1.0 - max(runs[c][t - 5] for c in cols) for t in never):.1f} pts")
