"""Why does the previous bot dominate mm2 in the arena but lose to it on the grader?

Decompose the head-to-head PnL by channel (RFQ fills vs FOK fills) for both bots
in identical sessions. Hypothesis: the arena's FOK flow is donation-rich, and the
old bot's permissive FOK gates (DUMB regime: lock up to 60% of budget, no edge
bump) hoover donations that mm2's strict gates (4% accept rate) decline. FOKs are
split among acceptors -- so unlike RFQs, declining one does not deny it to rivals.
"""
import importlib.util
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from arena2 import FLOWS, draw_params, run_session  # noqa: E402
from head_to_head import OldBotAdapter, load_old_bot  # noqa: E402
from Market_Maker_2 import Underlying as U2  # noqa: E402


def main():
    mod = load_old_bot()
    n = 40
    # channel PnL accumulators: name -> [rfq_pnl-ish proxy] via fill counts and locks
    stats = {"Hamza Khan": {"rfq_fills": 0, "fok_fills": 0, "rfq_lots": 0, "fok_lots": 0},
             "MM-prev (v9)": {"rfq_fills": 0, "fok_fills": 0, "rfq_lots": 0, "fok_lots": 0}}

    # monkey-patch Account.trade to tag channel: run_session calls trade() inside
    # the FOK loop first, then the RFQ loop; we wrap flow generators instead.
    import arena2

    orig_foks = arena2.Flow.foks
    orig_rfqs = arena2.Flow.rfqs
    channel = {"now": "fok"}

    def foks_tagged(self, *a, **k):
        channel["now"] = "fok"
        yield from orig_foks(self, *a, **k)

    def rfqs_tagged(self, *a, **k):
        channel["now"] = "rfq"
        yield from orig_rfqs(self, *a, **k)

    arena2.Flow.foks = foks_tagged
    arena2.Flow.rfqs = rfqs_tagged

    orig_trade = arena2.Account.trade

    def trade_tagged(self, oid, signed, price):
        name = getattr(self, "_owner", None)
        if name in stats:
            key = "fok" if channel["now"] == "fok" else "rfq"
            stats[name][f"{key}_fills"] += 1
            stats[name][f"{key}_lots"] += abs(signed)
        return orig_trade(self, oid, signed, price)

    arena2.Account.trade = trade_tagged

    orig_run = arena2.run_session

    def run_owned(mp, cfg, opps, cap, seed, days=25):
        # tag accounts with owner names right after creation via a wrapper on Account
        return orig_run(mp, cfg, opps, cap, seed, days)

    # simpler: patch Account.__init__ to remember insertion order via a queue
    pending = []
    orig_init = arena2.Account.__init__

    def init_owned(self, cash):
        orig_init(self, cash)
        if pending:
            self._owner = pending.pop(0)

    arena2.Account.__init__ = init_owned

    pnls = {"Hamza Khan": [], "MM-prev (v9)": []}
    for s in range(n):
        rng = random.Random(70000 + s)
        mp = draw_params(rng)
        rng2 = random.Random(70000 + s)
        _ = draw_params(rng2)
        v = {1: max(round(rng2.uniform(0.5, 5.0) * 4) / 4, 0.0),
             2: round(rng2.uniform(400, 1500), 2), 3: round(rng2.uniform(400, 1500), 2)}
        unds = [U2("FED", 1, v[1]), U2("AJR", 2, v[2]), U2("THR", 3, v[3])]
        adapter = OldBotAdapter(unds, [], 20.0, mod)
        pending.extend(["Hamza Khan", "MM-prev (v9)"])
        _, pnl = run_session(mp, FLOWS["neutral"], [adapter], 20.0, seed=70000 + s)
        for k in pnls:
            pnls[k].append(pnl.get(k, 0.0))

    print(f"{n} shared sessions, neutral flow")
    print(f"{'bot':>16}{'mean PnL':>10}{'RFQ fills':>11}{'RFQ lots':>10}{'FOK fills':>11}{'FOK lots':>10}")
    for name in stats:
        st = stats[name]
        print(f"{name:>16}{statistics.fmean(pnls[name]):>+10.2f}{st['rfq_fills']:>11}"
              f"{st['rfq_lots']:>10}{st['fok_fills']:>11}{st['fok_lots']:>10}")
    print("\nif prev's PnL edge concentrates in FOK lots, the head-to-head gap is an")
    print("artifact of the arena's donation-rich FOK flow (E53 family), NOT proof that")
    print("prev would beat mm2 on the grader (it verifiably does not: 14.6 vs 17.4).")


if __name__ == "__main__":
    main()
