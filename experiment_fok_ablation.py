"""FOK module ablation, matched seeds: is v5's FOK acceptance policy value-destroying?

Arms:
  A) v5 as-is
  B) FOK-OFF: reject every FOK (isolates the module's total contribution)
  C) FOK-SIGMA: accept only if edge >= max(v5 threshold, 1.0 * sigma_epsilon(option))
     (research arm - wires sigma into FOK for EXPERIMENT only, not shipping)
"""
import math
import random
import statistics
import sys

from Market_Maker import MarketMaker, OrderType, _price_with_model, _sigma_epsilon
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


class FokOffMM(MarketMaker):
    def respond_to_fok(self, option, fok_order) -> bool:
        try:
            # Keep the flow-IQ observation identical to v5 so regimes stay comparable.
            theo = self.price_option(option)
            edge = (fok_order.price - theo) if fok_order.order_type is OrderType.BUY else (theo - fok_order.price)
            self._flow_iq_ewma = 0.85 * self._flow_iq_ewma + 0.15 * min(max(edge, -0.25), 0.25)
            self._flow_iq_n += 1
        except Exception:
            pass
        return False


class FokSigmaMM(MarketMaker):
    def respond_to_fok(self, option, fok_order) -> bool:
        try:
            accept = super().respond_to_fok(option, fok_order)
            if not accept:
                return False
            theo = self.price_option(option)
            edge = (fok_order.price - theo) if fok_order.order_type is OrderType.BUY else (theo - fok_order.price)
            values = {u.underlying_id: u.value for u in self.underlying_state}
            model = self._model if self._model is not None else self._fallback_model()
            sigma = _sigma_epsilon(model, option, values)
            return edge >= sigma  # 1.0x quantile bound on top of every v5 gate
        except Exception:
            return False


class FokSigmaGatedMM(MarketMaker):
    """Sigma-bound applies ONLY outside the DUMB regime: uninformed crossers do not
    exploit estimation error, so the quantile penalty is pure opportunity cost there."""

    def respond_to_fok(self, option, fok_order) -> bool:
        try:
            accept = super().respond_to_fok(option, fok_order)
            if not accept:
                return False
            if self._regime() == self._DUMB:
                return True
            theo = self.price_option(option)
            edge = (fok_order.price - theo) if fok_order.order_type is OrderType.BUY else (theo - fok_order.price)
            values = {u.underlying_id: u.value for u in self.underlying_state}
            model = self._model if self._model is not None else self._fallback_model()
            sigma = _sigma_epsilon(model, option, values)
            return edge >= sigma
        except Exception:
            return False


def ci95(diffs):
    n = len(diffs)
    mean = statistics.fmean(diffs)
    sd = statistics.stdev(diffs) if n > 1 else 0.0
    half = 1.96 * sd / math.sqrt(max(n, 1))
    return mean, mean - half, mean + half


def main() -> None:
    MarketMaker.TELEMETRY = False
    confirm = "--confirm" in sys.argv
    gated = "--gated" in sys.argv
    n_seeds = 250 if (confirm or gated) else N_SEEDS
    if gated:
        seed_base, session_base = 80000, 90000   # third disjoint seed block
        arms = (("v5", MarketMaker), ("fok_sig_gated", FokSigmaGatedMM))
    elif confirm:
        seed_base, session_base = 40000, 60000
        arms = (("v5", MarketMaker), ("fok_sigma", FokSigmaMM))
    else:
        seed_base, session_base = 6000, 13000
        arms = (("v5", MarketMaker), ("fok_off", FokOffMM), ("fok_sigma", FokSigmaMM))
    print(f"=== FOK MODULE ABLATION ({'GATED confirmation' if gated else ('CONFIRMATION' if confirm else 'exploration')}; "
          f"{n_seeds} seeds x {len(WORLDS)} worlds x {len(arms)} arms, fresh seed block ===")
    grand = {name: [] for name, _ in arms}
    for world_name, spec in WORLDS.items():
        scores = {name: [] for name, _ in arms}
        pnls = {name: [] for name, _ in arms}
        for s in range(n_seeds):
            rng = random.Random(seed_base + s)
            params = _params(rng)
            for name, cls in arms:
                r = run_session(params, spec["flow"], spec["opp"](params), spec["capital"], DAYS,
                                seed=session_base + s, mm_factory=lambda u, o, c: cls(u, o, c))
                scores[name].append(r.our_score)
                pnls[name].append(r.pnl_by_name["Hamza Khan"])
                grand[name].append(r.our_score)
        line = f"  {world_name:<14}"
        for name, _ in arms:
            line += f"  {name}: {statistics.fmean(scores[name]):.3f}/{statistics.fmean(pnls[name]):+7.2f}"
        print(line)
        for alt, _ in arms[1:]:
            m, lo, hi = ci95([a - b for a, b in zip(scores[alt], scores["v5"])])
            flag = "SIG+" if lo > 0 else ("SIG-" if hi < 0 else "ns")
            print(f"      {alt}-v5: {m:+.4f} [{lo:+.4f},{hi:+.4f}] {flag}")

    print("\n=== GRAND (all worlds pooled) ===")
    for name, _ in arms:
        print(f"  {name:<10} mean score {statistics.fmean(grand[name]):.4f}")
    for alt, _ in arms[1:]:
        m, lo, hi = ci95([a - b for a, b in zip(grand[alt], grand["v5"])])
        flag = "SIG+" if lo > 0 else ("SIG-" if hi < 0 else "ns")
        print(f"  {alt}-v5 pooled: {m:+.4f} [{lo:+.4f},{hi:+.4f}] {flag}")


if __name__ == "__main__":
    main()
