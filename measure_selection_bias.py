"""Measure the RFQ winner's-curse selection bias directly (arena instrumentation).

Quantity: directional theo error at fill = sign(fill) * (V_hat - V_true).
Positive = our estimate was biased in the direction that made us WIN the auction
(overpaying on buys / undercharging on sells). Compare against the same bot's
UNCONDITIONAL directional error over all quoted options to isolate selection.
Arena-world caveat applies: opponents/flow are reconstructions (HYPOTHESIS-tier).
"""
import random
import statistics

from Market_Maker import MarketMaker
from sim_arena import FixedWidthBot, FlowConfig, StalemateBot, _MarketModel, _params, _price_with_model, run_session

N_SEEDS = 120
DAYS = 25

WORLDS: dict[str, dict] = {
    "vs_lattice+fw05 (n=2 sharp-ish pricers)": dict(
        flow=FlowConfig("neutral", rfq_per_day=3, fok_per_day=1, qty_lo=1, qty_hi=10), capital=20.0,
        opp=lambda p: [FixedWidthBot("Lattice", p, 0.16, size=25), FixedWidthBot("FW05", p, 0.05, size=25)]),
    "vs_fw10+stale (n=2 mixed)": dict(
        flow=FlowConfig("neutral", rfq_per_day=3, fok_per_day=1, qty_lo=1, qty_hi=10), capital=20.0,
        opp=lambda p: [FixedWidthBot("FW10", p, 0.10, size=25), StalemateBot("Stale", p)]),
    "vs_stale only (n=1)": dict(
        flow=FlowConfig("neutral", rfq_per_day=3, fok_per_day=1, qty_lo=1, qty_hi=10), capital=20.0,
        opp=lambda p: [StalemateBot("Stale", p)]),
}


def main() -> None:
    MarketMaker.TELEMETRY = False
    print("=== RFQ SELECTION BIAS: directional theo error, filled vs unconditional ===")
    print("(positive = biased toward winning; this is the winner's-curse premium)")

    for world_name, spec in WORLDS.items():
        fill_errs: list[float] = []
        uncond_errs: list[float] = []

        for s in range(N_SEEDS):
            rng = random.Random(3000 + s)
            params = _params(rng)
            true_model = _MarketModel.from_parameters(params)
            state = {"mm": None}

            def probe(agent, source, option, signed_qty, price, vals, _tm=true_model, _st=state):
                if agent != "Hamza Khan" or source != "rfq":
                    return
                mm = _st["mm"]
                if mm is None or mm._model is None:
                    return
                v_hat = _price_with_model(mm._model, option, vals)
                v_true = _price_with_model(_tm, option, vals)
                sign = 1.0 if signed_qty > 0 else -1.0
                fill_errs.append(sign * (v_hat - v_true))

            def factory(u, o, c, _st=state):
                mm = MarketMaker(u, o, c)
                _st["mm"] = mm
                return mm

            r = run_session(params, spec["flow"], spec["opp"](params), spec["capital"], DAYS,
                            seed=9000 + s, mm_factory=factory, fill_probe=probe)
            # Unconditional directional error benchmark: same bot, all final options, both signs
            mm = state["mm"]
            if mm is not None and mm._model is not None:
                vals = {u.underlying_id: u.value for u in mm.underlying_state}
                for option in mm.active_option_state:
                    e = _price_with_model(mm._model, option, vals) - _price_with_model(true_model, option, vals)
                    uncond_errs.append(e)   # buy direction
                    uncond_errs.append(-e)  # sell direction (symmetric benchmark)

        mu_fill = statistics.fmean(fill_errs) if fill_errs else float("nan")
        mu_unc = statistics.fmean(uncond_errs) if uncond_errs else float("nan")
        sd_unc = statistics.pstdev(uncond_errs) if len(uncond_errs) > 1 else float("nan")
        se_fill = (statistics.stdev(fill_errs) / len(fill_errs) ** 0.5) if len(fill_errs) > 2 else float("nan")
        print(f"\n{world_name}")
        print(f"  fills observed          : {len(fill_errs)}")
        print(f"  E[dir err | filled]     : {mu_fill:+.4f}  (SE {se_fill:.4f})")
        print(f"  E[dir err] uncond.      : {mu_unc:+.4f}  (sd {sd_unc:.4f})")
        if sd_unc and sd_unc > 0:
            print(f"  selection premium       : {mu_fill - mu_unc:+.4f}  = {(mu_fill - mu_unc) / sd_unc:+.2f} x sigma_eps")


if __name__ == "__main__":
    main()
