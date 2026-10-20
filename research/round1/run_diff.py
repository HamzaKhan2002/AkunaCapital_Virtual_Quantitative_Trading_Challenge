"""
Grader-output harness for MECHANISM testing (not parameter tuning).

The distinction matters. With 16 fixed-seed tests and ~20 tunable constants,
coordinate ascent on the score is overfitting by construction: 16 step-function
observations cannot identify 20 parameters, and a constant tuned until TC13's
$0.11 margin widens has not improved the policy, only its luck on one seed.

So this tool does not search. It enforces the rule that separates a mechanism
from a fit:

    a change is ACCEPTED only if the score improves AND every test the
    mechanism did not predict would move is byte-identical.

Score improvement alone is NOT sufficient. A mechanism that is supposed to fire
only against a 0.00-bidding opponent must be provably inert everywhere else; if
unrelated tests wobble, the mechanism is wrong even when the total goes up.

Usage
  python run_diff.py <run.txt>                      # table + margins + fragility
  python run_diff.py <base.txt> <cand.txt>          # what actually changed
  python run_diff.py <base.txt> <cand.txt> --expect TC5,TC16
                                                    # pre-registered prediction
"""
from __future__ import annotations

import re
import sys

ME = "Hamza Khan"
SCORED_FROM = 5          # TC1 = pricing, TC2-4 = verbose/unscored
BASE_POINTS = 4.0

_TEST = re.compile(r"Test Case (\d+):")
_RANK = re.compile(r"^\s*\d+\.\s+(.+?):\s+\$(-?\d+(?:\.\d+)?)\s*$", re.M)
_SCORE = re.compile(r"score=([0-9.]+)")
_CAP = re.compile(r"starting capital:\s*([\d.]+)")
_BANKRUPT = re.compile(r"bankrupt:\s*(True|False)")


def parse(path: str) -> dict[int, dict]:
    with open(path, encoding="utf-8", errors="ignore") as fh:
        text = fh.read()

    marks = [(m.start(), int(m.group(1))) for m in _TEST.finditer(text)]
    out: dict[int, dict] = {}
    for i, (pos, tc) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        block = text[pos:end]
        pnl = {name: float(v) for name, v in _RANK.findall(block)}
        if ME not in pnl:
            continue                                  # pricing test, no ranking
        score = _SCORE.search(block)
        cap = _CAP.search(block)
        bank = _BANKRUPT.search(block)
        out[tc] = {
            "me": pnl.pop(ME),
            "others": pnl,
            "score": float(score.group(1)) if score else None,
            "capital": float(cap.group(1)) if cap else None,
            "bankrupt": bank.group(1) == "True" if bank else None,
        }
    return out


def margins(rec: dict) -> tuple[float | None, float | None, int, int]:
    """(gain needed for next flip, cushion before losing one, beaten, total)."""
    me, others = rec["me"], list(rec["others"].values())
    above = [p for p in others if p > me]
    below = [p for p in others if p <= me]
    need = (min(above) - me) if above else None
    cushion = (me - max(below)) if below else None
    return need, cushion, len(below), len(others)


def show(runs: dict[int, dict], label: str) -> None:
    print(f"\n=== {label} ===")
    print(f"{'TC':<6}{'cap':>5}{'score':>7}{'us':>10}   "
          f"{'need':>8}{'cushion':>9}   opponents")
    total = 0.0
    fragile, reachable = [], []
    for tc in sorted(runs):
        r = runs[tc]
        need, cushion, beaten, n = margins(r)
        if tc >= SCORED_FROM and r["score"] is not None:
            total += r["score"]
        opp = ", ".join(f"{k} ${v:g}" for k, v in
                        sorted(r["others"].items(), key=lambda kv: -kv[1]))
        ns = f"{need:>8.2f}" if need is not None else f"{'-':>8}"
        cs = f"{cushion:>9.2f}" if cushion is not None else f"{'-':>9}"
        flag = ""
        if cushion is not None and cushion < 1.0:
            flag, _ = " <-- FRAGILE", fragile.append((tc, cushion))
        if need is not None and need < 6.0:
            reachable.append((tc, need))
        print(f"TC{tc:<4}{r['capital'] or 0:>5.0f}{r['score'] or 0:>7.2f}"
              f"{r['me']:>10.2f}   {ns}{cs}   {opp}{flag}")

    print(f"\n  total = {BASE_POINTS} + {total:.1f} = {BASE_POINTS + total:.1f}")
    if fragile:
        print("  FRAGILE (a rank we hold by under $1 -- any change risks it):")
        for tc, c in sorted(fragile, key=lambda x: x[1]):
            print(f"    TC{tc}: cushion ${c:.2f}")
    if reachable:
        print("  REACHABLE (one more rank within $6):")
        for tc, nd in sorted(reachable, key=lambda x: x[1]):
            print(f"    TC{tc}: need +${nd:.2f}")


def diff(a: dict, b: dict, expect: set[int] | None) -> int:
    moved = {}
    for tc in sorted(set(a) | set(b)):
        if tc not in a or tc not in b:
            moved[tc] = ("absent", None, None)
            continue
        if abs(a[tc]["me"] - b[tc]["me"]) > 1e-9 or a[tc]["others"] != b[tc]["others"]:
            moved[tc] = ("pnl", a[tc], b[tc])

    print("\n=== WHAT CHANGED ===")
    if not moved:
        print("  nothing -- the two runs are identical.")
    for tc, (kind, ra, rb) in moved.items():
        if kind == "absent":
            print(f"  TC{tc}: present in only one run")
            continue
        ds = (rb["score"] or 0) - (ra["score"] or 0)
        print(f"  TC{tc}: us ${ra['me']:.2f} -> ${rb['me']:.2f}   "
              f"score {ra['score']:.2f} -> {rb['score']:.2f} ({ds:+.2f})")
        for name in sorted(set(ra["others"]) | set(rb["others"])):
            x, y = ra["others"].get(name), rb["others"].get(name)
            if x != y:
                print(f"        {name}: ${x} -> ${y}")

    ta = sum(r["score"] or 0 for tc, r in a.items() if tc >= SCORED_FROM)
    tb = sum(r["score"] or 0 for tc, r in b.items() if tc >= SCORED_FROM)
    print(f"\n  total {BASE_POINTS + ta:.1f} -> {BASE_POINTS + tb:.1f} "
          f"({tb - ta:+.1f})")

    if expect is None:
        print("\n  (no prediction given -- pass --expect to enforce inertness)")
        return 0

    got = set(moved)
    unexpected = got - expect
    missing = expect - got
    print("\n=== INERTNESS CHECK ===")
    print(f"  predicted to move : {sorted(expect) or 'none'}")
    print(f"  actually moved    : {sorted(got) or 'none'}")
    if unexpected:
        print(f"  *** VIOLATION: moved but should not have: {sorted(unexpected)}")
        print("      The mechanism is not what you think it is. REJECT the change")
        print("      even if the total went up -- that is the overfitting signature.")
    if missing:
        print(f"  *** predicted to move but did not: {sorted(missing)}")
        print("      The mechanism did not fire. Diagnose before keeping.")
    if not unexpected and not missing:
        print("  PASS -- moved exactly where predicted. This is mechanism evidence,")
        print("  not a fit, and is the only kind of gain that should transfer to")
        print("  the hidden cases and to round 2.")
    return 1 if unexpected else 0


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    exp = None
    for a in argv:
        if a.startswith("--expect"):
            raw = a.split("=", 1)[1] if "=" in a else argv[argv.index(a) + 1]
            exp = {int(t.strip().lstrip("TCtc")) for t in raw.split(",") if t.strip()}

    if not args:
        print(__doc__)
        return 2
    if len(args) == 1:
        show(parse(args[0]), args[0])
        return 0
    a, b = parse(args[0]), parse(args[1])
    show(a, args[0])
    show(b, args[1])
    return diff(a, b, exp)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
