"""Ceiling / Gap Diagnosis: why does v5 lose rank?

Three matched-seed arms per world:
  A) v5 as-is (estimation + policy)
  B) ORACLE-PARAMS: v5 policy, TRUE MarketParameters injected (isolates estimation)
  C) per-fill attribution on arm A: realized edge vs true-value edge, by category

Failure-mode split per losing session: estimation / execution-width / adverse-fill /
inactivity (no fills where winner profited) / concentration variance.
"""
import math
import random
import statistics
from collections import defaultdict

from Market_Maker import (
    AJARAI_UNDERLYING_ID as AJR,
    FED_FUNDS_RATE_UNDERLYING_ID as FED,
    MarketMaker,
    _MarketModel,
    _price_with_model,
)
from sim_arena import FixedWidthBot, FlowConfig, StalemateBot, _params, run_session

N_SEEDS = 100
DAYS = 25

WORLDS: dict[str, dict] = {
    "lean_lattice": dict(
        flow=FlowConfig("neutral", rfq_per_day=2, fok_per_day=1, qty_lo=1, qty_hi=8), capital=20.0,
        opp=lambda p: [FixedWidthBot("Lattice", p, 0.16, size=25), FixedWidthBot("FW05", p, 0.05, size=25)]),
    "lean_fw10": dict(
        flow=FlowConfig("neutral", rfq_per_day=3, fok_per_day=1, qty_lo=1, qty_hi=10), capital=10.0,
        opp=lambda p: [FixedWidthBot("FW10", p, 0.10, size=25), StalemateBot("Stale", p)]),
    "lean_sharp": dict(
        flow=FlowConfig("sharp", rfq_per_day=2, fok_per_day=2, qty_lo=1, qty_hi=8), capital=40.0,
        opp=lambda p: [FixedWidthBot("Lattice", p, 0.16, size=25), FixedWidthBot("SU", p, 0.30, size=15)]),
    "dumb_stale": dict(
        flow=FlowConfig("dumb", rfq_per_day=3, fok_per_day=2, qty_lo=2, qty_hi=12), capital=10.0,
        opp=lambda p: [StalemateBot("Stale", p)]),
}


class OracleMM(MarketMaker):
    """v5 policy, true parameters injected — isolates estimation error from policy."""

    _true_params = None

    def warm_up(self, market_history) -> None:
        try:
            self._model = _MarketModel.from_parameters(self._true_params)
        except Exception:
            self._model = None


def option_category(option) -> str:
    uids = {leg.underlying_id for leg in option.legs}
    if len(uids) > 1:
        return "spread"
    return "FED" if FED in uids else "single"


def run_world(world_name: str, spec: dict):
    rows = []
    fills_by_cat = defaultdict(lambda: {"lots": 0, "true_edge": 0.0, "est_edge": 0.0})

    for s in range(N_SEEDS):
        rng = random.Random(4000 + s)
        params = _params(rng)
        true_model = _MarketModel.from_parameters(params)
        state = {"mm": None}

        def probe(agent, source, option, signed_qty, price, vals,
                  _tm=true_model, _st=state, _f=fills_by_cat):
            if agent != "Hamza Khan":
                return
            mm = _st["mm"]
            v_true = _price_with_model(_tm, option, vals)
            v_hat = _price_with_model(mm._model, option, vals) if (mm and mm._model) else v_true
            sign = 1.0 if signed_qty > 0 else -1.0
            lots = abs(signed_qty)
            cat = option_category(option) + ("_" + source)
            _f[cat]["lots"] += lots
            _f[cat]["true_edge"] += lots * sign * (v_true - price)
            _f[cat]["est_edge"] += lots * sign * (v_hat - price)

        def factory(u, o, c, _st=state):
            mm = MarketMaker(u, o, c)
            _st["mm"] = mm
            return mm

        r_base = run_session(params, spec["flow"], spec["opp"](params), spec["capital"], DAYS,
                             seed=11000 + s, mm_factory=factory, fill_probe=probe)

        OracleMM._true_params = params
        r_oracle = run_session(params, spec["flow"], spec["opp"](params), spec["capital"], DAYS,
                               seed=11000 + s, mm_factory=lambda u, o, c: OracleMM(u, o, c))

        rows.append((r_base, r_oracle))
    return rows, fills_by_cat


def main() -> None:
    MarketMaker.TELEMETRY = False
    print("=== CEILING / GAP DIAGNOSIS ===")
    grand = {"base_score": [], "oracle_score": [], "base_pnl": [], "oracle_pnl": []}

    for world_name, spec in WORLDS.items():
        rows, fills = run_world(world_name, spec)
        b_scores = [b.our_score for b, _ in rows]
        o_scores = [o.our_score for _, o in rows]
        b_pnl = [b.pnl_by_name["Hamza Khan"] for b, _ in rows]
        o_pnl = [o.pnl_by_name["Hamza Khan"] for _, o in rows]
        grand["base_score"] += b_scores
        grand["oracle_score"] += o_scores
        grand["base_pnl"] += b_pnl
        grand["oracle_pnl"] += o_pnl

        diffs = [o - b for b, o in zip(b_scores, o_scores)]
        mean_d = statistics.fmean(diffs)
        se = statistics.stdev(diffs) / math.sqrt(len(diffs)) if len(diffs) > 1 else 0.0
        print(f"\n--- {world_name} ---")
        print(f"  score:  v5 {statistics.fmean(b_scores):.3f}  oracle-params {statistics.fmean(o_scores):.3f}"
              f"  diff {mean_d:+.4f} (SE {se:.4f}) {'SIG' if abs(mean_d) > 2 * se and se > 0 else 'ns'}")
        print(f"  PnL:    v5 {statistics.fmean(b_pnl):+8.2f}  oracle-params {statistics.fmean(o_pnl):+8.2f}")
        print(f"  {'category':<16}{'lots':>7}{'true edge/lot':>15}{'est edge/lot':>14}{'illusory/lot':>14}")
        for cat, d in sorted(fills.items()):
            if d["lots"] == 0:
                continue
            te = d["true_edge"] / d["lots"]
            ee = d["est_edge"] / d["lots"]
            print(f"  {cat:<16}{d['lots']:>7}{te:>15.4f}{ee:>14.4f}{ee - te:>14.4f}")

    print("\n=== GRAND SUMMARY ===")
    bs, os_ = statistics.fmean(grand["base_score"]), statistics.fmean(grand["oracle_score"])
    print(f"v5 score {bs:.4f} -> oracle-params score {os_:.4f}   estimation share of gap: {os_ - bs:+.4f}")
    print(f"v5 PnL {statistics.fmean(grand['base_pnl']):+.2f} -> oracle PnL {statistics.fmean(grand['oracle_pnl']):+.2f}")
    print("\nNote: oracle-params holds POLICY fixed; residual deficit vs 1.0 under oracle = execution/policy share.")


if __name__ == "__main__":
    main()
