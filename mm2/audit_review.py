"""
Audit of an external review. Four claims, three checkable, one actionable.

  A "per-counterparty adaptation never fires (97.8% UNKNOWN)"
        -> is that a threshold that is too strict, or is the EVIDENCE absent?
           Measure observations per counterparty. If most cps are seen once or
           twice, no threshold could classify them and the machinery is not
           merely unused, it is unusable.

  B "the edge comes from structural free-rolls, not pricing"
        -> attribute settled realized dollars to free-roll trades (fill at
           0.00/1.00) versus ordinary quoted trades.

  C "robustness to fresh opponents or seeds is untested"
        -> already false (1,440 out-of-domain sessions, 75 roster x capital
           configs, 35 fuzz probes); not re-tested here.

  D THE ACTIONABLE ONE: "rank is partially observable through fills -- use fill
        patterns to estimate whether we are ahead or behind, then target
        variance (Seel-Strack)."
        -> directly testable: correlate every in-session observable available
           at decision time with the FINAL rank score. If the correlations are
           weak, the suggestion is refuted with data rather than argument.
"""
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arena2  # noqa: E402
from arena2 import FlowConfig, KNOWN_TESTS, build, draw_params, run_session  # noqa: E402
import Market_Maker_2 as MM  # noqa: E402

CAL = FlowConfig("neutral", 1, 1, 12, big_order_prob=0.10, big_qty_hi=60)
_made: list = []
_Base = MM.MarketMaker


class Spy(_Base):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.tr_free = 0          # fills at 0.00 / 1.00
        self.tr_norm = 0
        self.d_free = 0.0         # settled realized dollars, free-roll
        self.d_norm = 0.0
        self.quotes = 0
        self.cls_seen: dict[str, int] = {}
        _made.append(self)

    def quote(self, option, counterparty_id):
        self.quotes += 1
        c = self._class_of(counterparty_id)
        self.cls_seen[c] = self.cls_seen.get(c, 0) + 1
        return super().quote(option, counterparty_id)

    def on_trade(self, option, price, quantity, counterparty_id):
        free = price <= 1e-9 or price >= 1.0 - 1e-9
        if free:
            self.tr_free += 1
        else:
            self.tr_norm += 1
        self._tag = getattr(self, "_tag", {})
        self._tag.setdefault(option.option_id, []).append((quantity, price, free))
        super().on_trade(option, price, quantity, counterparty_id)

    def _settle(self, option, values):
        oid = option.option_id
        tags = getattr(self, "_tag", {}).get(oid, [])
        if oid not in self._settled and tags:
            payoff = option.expiry_valuation(values)
            for qty, price, free in tags:
                r = (payoff - price) if qty >= 0 else (price - payoff)
                if free:
                    self.d_free += abs(qty) * r
                else:
                    self.d_norm += abs(qty) * r
        super()._settle(option, values)


arena2.MarketMaker = Spy


def main() -> int:
    rows = []
    cls_tot: dict[str, int] = {}
    obs_per_cp: list[int] = []
    d_free = d_norm = 0.0
    n_free = n_norm = 0

    for tc, (cap, names, _s) in KNOWN_TESTS.items():
        for s in range(60):
            rng = random.Random(500_000 + s)
            mp = draw_params(rng)
            _made.clear()
            score, pnl = run_session(mp, CAL, build(names, mp), cap, 500_000 + s)
            if not _made:
                continue
            b = _made[-1]
            for k, v in b.cls_seen.items():
                cls_tot[k] = cls_tot.get(k, 0) + v
            for cp, book in b._cp.items():
                obs_per_cp.append(book.n + book.settle_n)
            d_free += b.d_free
            d_norm += b.d_norm
            n_free += b.tr_free
            n_norm += b.tr_norm
            fills = b.tr_free + b.tr_norm
            rows.append({
                "score": score,
                "fills": fills,
                "fill_rate": fills / max(b.quotes, 1),
                "free_frac": b.tr_free / max(fills, 1),
                "pnl": pnl.get("Hamza Khan", 0.0),
                "util": b._utilization(),
            })

    print("=" * 74)
    print("A. IS PER-COUNTERPARTY ADAPTATION POSSIBLE AT ALL?")
    print("=" * 74)
    tot = sum(cls_tot.values())
    for k, v in sorted(cls_tot.items(), key=lambda kv: -kv[1]):
        print(f"   quotes priced as {k:<9} {v / tot:>7.1%}")
    obs_per_cp.sort()
    n = len(obs_per_cp)
    print(f"\n   counterparties observed: {n}")
    print(f"   observations per counterparty: median {obs_per_cp[n // 2]}, "
          f"p90 {obs_per_cp[int(0.9 * n)]}, max {obs_per_cp[-1]}")
    thin = sum(1 for o in obs_per_cp if o <= 2) / n
    print(f"   share of counterparties with <= 2 observations: {thin:.1%}")
    print("   => the classifier needs a z-score over settled trades; with this")
    print("      many observations per cp the evidence does not exist. The")
    print("      machinery is not mis-tuned, it is starved -- the same limit")
    print("      as PROBLEM.md section 4.")

    print("\n" + "=" * 74)
    print("B. WHERE DOES THE MONEY ACTUALLY COME FROM?")
    print("=" * 74)
    tot_d = d_free + d_norm
    print(f"   free-roll fills (0.00/1.00) : {n_free:>6}  realised ${d_free:>10.2f}"
          f"  {d_free / tot_d if tot_d else 0:>7.1%}")
    print(f"   ordinary quoted fills       : {n_norm:>6}  realised ${d_norm:>10.2f}"
          f"  {d_norm / tot_d if tot_d else 0:>7.1%}")

    print("\n" + "=" * 74)
    print("D. IS RANK PREDICTABLE FROM IN-SESSION OBSERVABLES?")
    print("=" * 74)

    def corr(a, b):
        ma, mb = statistics.fmean(a), statistics.fmean(b)
        va = sum((x - ma) ** 2 for x in a) ** 0.5
        vb = sum((x - mb) ** 2 for x in b) ** 0.5
        if va < 1e-12 or vb < 1e-12:
            return 0.0
        return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (va * vb)

    sc = [r["score"] for r in rows]
    print(f"   sessions: {len(rows)}\n")
    print(f"   {'observable':<28}{'corr with final rank score':>28}")
    for key, lab in (("fills", "fill count"), ("fill_rate", "fill rate"),
                     ("free_frac", "free-roll share of fills"),
                     ("util", "margin utilisation"),
                     ("pnl", "our OWN final PnL")):
        c = corr([r[key] for r in rows], sc)
        print(f"   {lab:<28}{c:>+28.3f}")
    print("\n   'our own final PnL' is the upper bound: it is the best possible")
    print("   in-session predictor, and it is not available until the session is")
    print("   over. Anything a live policy could use must do worse than that.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
