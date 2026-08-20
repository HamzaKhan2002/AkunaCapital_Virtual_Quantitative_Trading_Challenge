"""Shrinkage-only A/B: v5 baseline vs v5 + SHRINK_ESTIMATOR, matched seeds (CRN).

One causal factor changes (the estimator flag). Same seed => same parameters, same
warm-up history, same value path, same flow stream, same opponents. Paired analysis.
"""
import math
import statistics

from Market_Maker import MarketMaker
from sim_arena import ARCHETYPES, _params, run_session

N_SEEDS = 120
DAYS = 25


class ShrunkMM(MarketMaker):
    SHRINK_ESTIMATOR = True


def run_arm(mm_cls, archetype_spec, params, capital, seed):
    return run_session(
        params, archetype_spec["flow"], archetype_spec["opp"](params), capital, DAYS, seed,
        mm_factory=lambda u, o, c: mm_cls(u, o, c),
    )


def ci95(diffs):
    n = len(diffs)
    mean = statistics.fmean(diffs)
    sd = statistics.stdev(diffs) if n > 1 else 0.0
    half = 1.96 * sd / math.sqrt(n)
    return mean, mean - half, mean + half


def main() -> None:
    MarketMaker.TELEMETRY = False
    import random

    per_arch = {}
    all_diffs = []
    agg = {arm: {"score": [], "pnl": [], "rmse": [], "fills": [], "lots": [], "minbal": [], "bankrupt": 0}
           for arm in ("base", "shrunk")}

    for arch_name, spec in ARCHETYPES.items():
        diffs = []
        for s in range(N_SEEDS):
            rng = random.Random(1000 + s)
            params = _params(rng)
            res = {}
            for arm, cls in (("base", MarketMaker), ("shrunk", ShrunkMM)):
                r = run_arm(cls, spec, params, spec["capital"], seed=5000 + s)
                res[arm] = r
                a = agg[arm]
                a["score"].append(r.our_score)
                a["pnl"].append(r.pnl_by_name["Hamza Khan"])
                a["rmse"].append(r.theo_rmse)
                a["fills"].append(r.our_fills)
                a["lots"].append(r.our_lots)
                a["minbal"].append(r.our_min_balance)
                a["bankrupt"] += int(r.bankrupt_by_name["Hamza Khan"])
            d = res["shrunk"].our_score - res["base"].our_score
            diffs.append(d)
            all_diffs.append(d)
        per_arch[arch_name] = ci95(diffs)

    print("=== SHRINKAGE-ONLY A/B (matched seeds, paired) ===")
    print(f"sessions per arm: {len(all_diffs)}  ({len(ARCHETYPES)} archetypes x {N_SEEDS} seeds)")
    print(f"\n{'metric':<16}{'v5 base':>12}{'v5+shrink':>12}")
    for key, fmt in (("score", ".4f"), ("pnl", ".2f"), ("rmse", ".4f"),
                     ("fills", ".1f"), ("lots", ".0f"), ("minbal", ".2f")):
        b = statistics.fmean(agg["base"][key])
        sh = statistics.fmean(agg["shrunk"][key])
        print(f"{key:<16}{b:>12{fmt}}{sh:>12{fmt}}")
    print(f"{'bankruptcies':<16}{agg['base']['bankrupt']:>12}{agg['shrunk']['bankrupt']:>12}")

    mean, lo, hi = ci95(all_diffs)
    print(f"\nPAIRED SCORE DIFF (shrunk - base): {mean:+.4f}  [95% CI {lo:+.4f}, {hi:+.4f}]")
    nz = sum(1 for d in all_diffs if d != 0)
    print(f"sessions where score changed: {nz}/{len(all_diffs)} "
          f"(+{sum(1 for d in all_diffs if d > 0)}, -{sum(1 for d in all_diffs if d < 0)})")
    print("\nper archetype (mean diff [95% CI]):")
    for name, (m, l, h) in per_arch.items():
        flag = "SIG+" if l > 0 else ("SIG-" if h < 0 else "ns")
        print(f"  {name:<22} {m:+.4f}  [{l:+.4f}, {h:+.4f}]  {flag}")

    rmse_b = statistics.fmean(agg["base"]["rmse"])
    rmse_s = statistics.fmean(agg["shrunk"]["rmse"])
    print(f"\ntheo RMSE: {rmse_b:.4f} -> {rmse_s:.4f}  ({100 * (1 - rmse_s / max(rmse_b, 1e-12)):+.1f}%)")


if __name__ == "__main__":
    main()
