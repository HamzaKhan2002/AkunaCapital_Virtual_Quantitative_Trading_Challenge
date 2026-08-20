"""Policy-family ceiling bound: lambda sweep UNDER ORACLE PARAMETERS in the worst world.

If no lambda closes the lean_lattice gap even with TRUE parameters, the deficit is
structural to the lambda-book family vs tight pricers in lean flow — evidence for
'replace module' over 'tune coefficient'. Research-only; nothing ships from here.
"""
import random
import statistics

from Market_Maker import MarketMaker, _MarketModel
from sim_arena import FixedWidthBot, FlowConfig, _params, run_session

N_SEEDS = 100
DAYS = 25

WORLD = dict(
    flow=FlowConfig("neutral", rfq_per_day=2, fok_per_day=1, qty_lo=1, qty_hi=8), capital=20.0,
    opp=lambda p: [FixedWidthBot("Lattice", p, 0.16, size=25), FixedWidthBot("FW05", p, 0.05, size=25)])


def make_cls(lam: float):
    class OracleLamMM(MarketMaker):
        LAMBDA_NEUTRAL = lam
        _true_params = None

        def warm_up(self, market_history) -> None:
            try:
                self._model = _MarketModel.from_parameters(self._true_params)
            except Exception:
                self._model = None

    return OracleLamMM


def main() -> None:
    MarketMaker.TELEMETRY = False
    lams = (0.60, 0.72, 0.80, 0.88, 0.94)
    print("=== LAMBDA SWEEP UNDER ORACLE PARAMS, lean_lattice world ===")
    print(f"{'lambda':>8}{'score':>9}{'pnl':>9}{'fills':>8}{'bankrupt':>10}")
    for lam in lams:
        cls = make_cls(lam)
        scores, pnls, fills, bk = [], [], [], 0
        for s in range(N_SEEDS):
            rng = random.Random(15000 + s)
            params = _params(rng)
            cls._true_params = params
            r = run_session(params, WORLD["flow"], WORLD["opp"](params), WORLD["capital"], DAYS,
                            seed=17000 + s, mm_factory=lambda u, o, c: cls(u, o, c))
            scores.append(r.our_score)
            pnls.append(r.pnl_by_name["Hamza Khan"])
            fills.append(r.our_fills)
            bk += int(r.bankrupt_by_name["Hamza Khan"])
        print(f"{lam:>8.2f}{statistics.fmean(scores):>9.3f}{statistics.fmean(pnls):>9.2f}"
              f"{statistics.fmean(fills):>8.1f}{bk:>10}")


if __name__ == "__main__":
    main()
