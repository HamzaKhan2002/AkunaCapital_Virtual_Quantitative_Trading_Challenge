"""Shrinkage A/B on HARD archetypes: lean flow (grader-realistic order rates) and
stronger opponents, to de-saturate the arena score metric (base arena sits at 0.985).

VERBOSE grader logs show ~2-4 orders/day total and qty 1-26; the standard arena uses
5-8/day and rich crossing. This set: rfq 2/day, fok 1/day, qty 1-8, true-theo opponents.
"""
import math
import random
import statistics

from Market_Maker import MarketMaker
from sim_arena import FixedWidthBot, FlowConfig, StalemateBot, _params, run_session

N_SEEDS = 150
DAYS = 25


class ShrunkMM(MarketMaker):
    SHRINK_ESTIMATOR = True


HARD: dict[str, dict] = {
    "lean_lattice_neutral": dict(
        flow=FlowConfig("neutral", rfq_per_day=2, fok_per_day=1, qty_lo=1, qty_hi=8), capital=20.0,
        opp=lambda p: [FixedWidthBot("Lattice", p, 0.16, size=25), FixedWidthBot("Fixed Width 0.05", p, 0.05, size=25)]),
    "lean_fw10_grind": dict(
        flow=FlowConfig("neutral", rfq_per_day=3, fok_per_day=1, qty_lo=1, qty_hi=10), capital=10.0,
        opp=lambda p: [FixedWidthBot("Fixed Width 0.1", p, 0.10, size=25), StalemateBot("Stalemate Quoter", p)]),
    "lean_sharp": dict(
        flow=FlowConfig("sharp", rfq_per_day=2, fok_per_day=2, qty_lo=1, qty_hi=8), capital=40.0,
        opp=lambda p: [FixedWidthBot("Lattice", p, 0.16, size=25), FixedWidthBot("Situational", p, 0.30, size=15)]),
    "lean_dumb_thin": dict(
        flow=FlowConfig("dumb", rfq_per_day=1, fok_per_day=1, qty_lo=1, qty_hi=6), capital=10.0,
        opp=lambda p: [StalemateBot("Stalemate Quoter", p)]),
}


def ci95(diffs):
    n = len(diffs)
    mean = statistics.fmean(diffs)
    sd = statistics.stdev(diffs) if n > 1 else 0.0
    half = 1.96 * sd / math.sqrt(n)
    return mean, mean - half, mean + half


def main() -> None:
    MarketMaker.TELEMETRY = False
    per_arch, all_diffs = {}, []
    agg = {arm: {"score": [], "pnl": [], "rmse": [], "fills": [], "bankrupt": 0} for arm in ("base", "shrunk")}

    for arch_name, spec in HARD.items():
        diffs = []
        for s in range(N_SEEDS):
            rng = random.Random(2000 + s)
            params = _params(rng)
            res = {}
            for arm, cls in (("base", MarketMaker), ("shrunk", ShrunkMM)):
                r = run_session(params, spec["flow"], spec["opp"](params), spec["capital"], DAYS,
                                seed=7000 + s, mm_factory=lambda u, o, c: cls(u, o, c))
                res[arm] = r
                a = agg[arm]
                a["score"].append(r.our_score)
                a["pnl"].append(r.pnl_by_name["Hamza Khan"])
                a["rmse"].append(r.theo_rmse)
                a["fills"].append(r.our_fills)
                a["bankrupt"] += int(r.bankrupt_by_name["Hamza Khan"])
            d = res["shrunk"].our_score - res["base"].our_score
            diffs.append(d)
            all_diffs.append(d)
        per_arch[arch_name] = ci95(diffs)

    print("=== SHRINKAGE A/B on HARD archetypes (lean flow, strong opponents) ===")
    print(f"sessions per arm: {len(all_diffs)}")
    print(f"\n{'metric':<14}{'v5 base':>12}{'v5+shrink':>12}")
    for key, fmt in (("score", ".4f"), ("pnl", ".2f"), ("rmse", ".4f"), ("fills", ".1f")):
        print(f"{key:<14}{statistics.fmean(agg['base'][key]):>12{fmt}}{statistics.fmean(agg['shrunk'][key]):>12{fmt}}")
    print(f"{'bankruptcies':<14}{agg['base']['bankrupt']:>12}{agg['shrunk']['bankrupt']:>12}")

    mean, lo, hi = ci95(all_diffs)
    print(f"\nPAIRED SCORE DIFF (shrunk - base): {mean:+.4f}  [95% CI {lo:+.4f}, {hi:+.4f}]")
    print(f"changed: {sum(1 for d in all_diffs if d != 0)}/{len(all_diffs)} "
          f"(+{sum(1 for d in all_diffs if d > 0)}, -{sum(1 for d in all_diffs if d < 0)})")
    for name, (m, l, h) in per_arch.items():
        flag = "SIG+" if l > 0 else ("SIG-" if h < 0 else "ns")
        print(f"  {name:<24} {m:+.4f}  [{l:+.4f}, {h:+.4f}]  {flag}")


if __name__ == "__main__":
    main()
