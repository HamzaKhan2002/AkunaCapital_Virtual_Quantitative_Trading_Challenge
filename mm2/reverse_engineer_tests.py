"""Reverse-engineer the grader's test-case structure from every saved log.

Extracts, per test: starting capital, roster (which opponent archetypes are
present), our PnL, each opponent's PnL, and the score. Aggregates across runs to
find which facts are FIXED (structural properties of the test) versus which move
with our behavior (and are therefore ours to influence).
"""
import glob
import re
from collections import Counter, defaultdict

files = sorted(glob.glob("**/Compiler_Messages_Run_*.txt", recursive=True),
               key=lambda p: int(re.search(r"Run_(\d+)", p).group(1)))

tests = defaultdict(dict)   # tc -> run -> {"cap":, "board": {name: pnl}, "score":}
for path in files:
    run = int(re.search(r"Run_(\d+)", path).group(1))
    txt = open(path, encoding="utf-8", errors="ignore").read()
    blocks = re.split(r"Test Case (\d+):", txt)[1:]
    for tc, body in zip(map(int, blocks[0::2]), blocks[1::2]):
        cap = re.search(r"starting capital:\s*([0-9.]+)", body)
        board = re.findall(r"\d+\.\s+(.+?):\s+\$(-?[0-9.]+)", body)
        score = re.search(r"score=([0-9.]+)", body)
        if not cap or not board:
            continue
        tests[tc][run] = {"cap": float(cap.group(1)),
                          "board": {n: float(v) for n, v in board},
                          "score": float(score.group(1)) if score else None}

print("=" * 78)
print("TEST-CASE STRUCTURE (fixed properties, identical in every run)")
print("=" * 78)
print(f"{'TC':>4}{'capital':>9}{'players':>9}  opponents (archetypes present)")
caps = Counter()
roster_freq = Counter()
for tc in sorted(tests):
    runs = tests[tc]
    capset = {r["cap"] for r in runs.values()}
    rosters = {tuple(sorted(n for n in r["board"] if n != "Hamza Khan")) for r in runs.values()}
    fixed_cap = capset.pop() if len(capset) == 1 else None
    roster = sorted(rosters, key=len)[-1]
    n_players = len(roster) + 1
    caps[fixed_cap] += 1
    roster_freq[roster] += 1
    warn = "" if len(capset) == 0 and len(rosters) == 1 else "  <-- VARIES ACROSS RUNS"
    print(f"{tc:>4}{fixed_cap:>9.0f}{n_players:>9}  {', '.join(roster)}{warn}")

print(f"\ncapital distribution across the 16 scored tests: "
      + ", ".join(f"${int(k)}x{v}" for k, v in sorted(caps.items())))
print(f"\ndistinct rosters ({len(roster_freq)}):")
for r, c in roster_freq.most_common():
    print(f"   x{c}  {', '.join(r) if r else '(none)'}")

print("\n" + "=" * 78)
print("OPPONENT PnL STABILITY  (low spread => opponent barely reacts to us =>")
print("its behaviour is simple/mechanical and therefore reproducible offline)")
print("=" * 78)
opp_stats = defaultdict(list)
for tc in sorted(tests):
    for run, r in tests[tc].items():
        for name, pnl in r["board"].items():
            if name != "Hamza Khan":
                opp_stats[(tc, name)].append(pnl)
by_opp = defaultdict(list)
for (tc, name), vals in opp_stats.items():
    by_opp[name].append((tc, min(vals), max(vals), max(vals) - min(vals)))
print(f"{'opponent':>26}{'tests':>7}{'mean spread':>13}{'max spread':>12}  interpretation")
for name in sorted(by_opp):
    rows = by_opp[name]
    spreads = [s for *_, s in rows]
    mean_s = sum(spreads) / len(spreads)
    interp = ("highly reactive to us" if mean_s > 8 else
              "mildly reactive" if mean_s > 3 else "near-static / mechanical")
    print(f"{name:>26}{len(rows):>7}{mean_s:>13.2f}{max(spreads):>12.2f}  {interp}")
