"""Local arena: faithful reconstruction of the grader from starter code + observed logs.

Ground truth reused directly: MarketParameters.advance_step (dynamics), Problem_2 margining
(max-loss debit per trade, end-of-day solvency, expiry credits), RFQ best-price routing with
spillover, FOK broadcast with equal split, score = 0.4 + 0.6 * beaten/competitors.

Assumptions (flagged, not verified): opponent bots price from TRUE parameters; flow archetypes
(dumb / neutral / sharp) inferred from VERBOSE logs and PnL signatures.
"""
from __future__ import annotations

import math
import random
import statistics
from collections import defaultdict
from dataclasses import dataclass, field

from Market_Maker import (
    AJARAI_UNDERLYING_ID as AJR,
    FED_FUNDS_RATE_UNDERLYING_ID as FED,
    THERIODIC_UNDERLYING_ID as THR,
    BinaryOption,
    FokOrder,
    MarketHistory,
    MarketMaker,
    MarketParameters,
    OptionLeg,
    OrderType,
    Quote,
    Underlying,
    _MarketModel,
    _price_with_model,
)


def _round_penny(x: float) -> float:
    return min(max(round(x, 2), 0.0), 1.0)


# --------------------------------------------------------------------- opponents

class _TrueTheoBot:
    """Base opponent: prices from the true parameters, like Akuna's battle-tested bots."""

    def __init__(self, name: str, params: MarketParameters) -> None:
        self.name = name
        self._model = _MarketModel.from_parameters(params)
        self.values: dict[int, float] = {}

    def warm_up(self, history: MarketHistory) -> None:
        pass

    def on_step_advance(self, underlyings: list[Underlying], options: list[BinaryOption]) -> None:
        self.values = {u.underlying_id: u.value for u in underlyings}

    def on_trade(self, option: BinaryOption, price: float, quantity: int, counterparty_id: int) -> None:
        pass

    def theo(self, option: BinaryOption) -> float:
        return _price_with_model(self._model, option, self.values)


class FixedWidthBot(_TrueTheoBot):
    def __init__(self, name: str, params: MarketParameters, width: float, size: int = 25) -> None:
        super().__init__(name, params)
        self.width = width
        self.size = size

    def quote(self, option: BinaryOption, counterparty_id: int) -> Quote:
        theo = self.theo(option)
        bid = _round_penny(theo - self.width / 2)
        offer = _round_penny(theo + self.width / 2)
        bid = min(bid, 0.99)
        offer = max(offer, bid + 0.01)
        return Quote(bid, self.size, offer, self.size)

    def respond_to_fok(self, option: BinaryOption, fok: FokOrder) -> bool:
        theo = self.theo(option)
        if fok.order_type is OrderType.BUY:
            return fok.price - theo >= self.width / 2
        return theo - fok.price >= self.width / 2


class StalemateBot(_TrueTheoBot):
    def quote(self, option: BinaryOption, counterparty_id: int) -> Quote:
        return Quote(0.0, 400, 1.0, 400)  # confirmed from TC2 logs: 0.00/1.00, ties split equally

    def respond_to_fok(self, option: BinaryOption, fok: FokOrder) -> bool:
        theo = self.theo(option)
        if fok.order_type is OrderType.BUY:
            return fok.price >= 0.99 and theo < 0.9
        return fok.price <= 0.01 and theo > 0.1


# --------------------------------------------------------------------- flow models

@dataclass
class FlowConfig:
    kind: str            # "dumb" | "neutral" | "sharp"
    rfq_per_day: int
    fok_per_day: int
    qty_lo: int = 2
    qty_hi: int = 40


class FlowGenerator:
    """Counterparties. 'sharp' flow peeks at tomorrow's values (pre-generated path)."""

    def __init__(self, cfg: FlowConfig, model: _MarketModel, rng: random.Random) -> None:
        self.cfg = cfg
        self.model = model
        self.rng = rng
        self.cp_pool = [self.rng.randrange(100000, 999999) for _ in range(6)]

    def _theo(self, option: BinaryOption, values: dict[int, float]) -> float:
        return _price_with_model(self.model, option, values)

    def fok_orders(self, options, values, next_values):
        out = []
        for _ in range(self.cfg.fok_per_day):
            option = self.rng.choice(options)
            theo = self._theo(option, values)
            qty = self.rng.randint(self.cfg.qty_lo, self.cfg.qty_hi)
            cp = self.rng.choice(self.cp_pool)
            if self.cfg.kind == "dumb":
                buy = self.rng.random() < 0.5
                shift = self.rng.uniform(0.05, 0.5)
                price = theo + shift if buy else theo - shift
            elif self.cfg.kind == "neutral":
                buy = self.rng.random() < 0.5
                price = theo + self.rng.gauss(0.0, 0.05)
            else:  # sharp: trade toward tomorrow's informed theo, cross slightly through today's
                informed = self._theo(option.advance_step(), next_values) if option.steps_until_expiry > 0 else theo
                if abs(informed - theo) < 0.03:
                    continue
                buy = informed > theo
                price = theo + (0.02 if buy else -0.02)
            price = min(max(round(price, 2), 0.01), 0.99)
            out.append((option, FokOrder(counterparty_id=cp, option_id=option.option_id,
                                         order_type=OrderType.BUY if buy else OrderType.SELL,
                                         price=price, quantity=qty)))
        return out

    def rfq_orders(self, options, values, next_values):
        out = []
        for _ in range(self.cfg.rfq_per_day):
            option = self.rng.choice(options)
            qty = self.rng.randint(self.cfg.qty_lo, self.cfg.qty_hi)
            cp = self.rng.choice(self.cp_pool)
            if self.cfg.kind == "sharp":
                theo = self._theo(option, values)
                informed = self._theo(option.advance_step(), next_values) if option.steps_until_expiry > 0 else theo
                if abs(informed - theo) < 0.03:
                    continue
                buy = informed > theo
                limit = None  # crosses whatever best price is (has edge anyway)
            else:
                buy = self.rng.random() < 0.5
                limit = None
            out.append((option, buy, qty, cp, limit))
        return out


# --------------------------------------------------------------------- margin engine

class Account:
    def __init__(self, cash: float) -> None:
        self.start = cash
        self.balance = cash
        self.bankrupt = False
        self.ledgers: dict[int, list[tuple[int, float]]] = defaultdict(list)  # option_id -> [(signed qty, price)]
        self.n_fills = 0
        self.lots = 0
        self.min_balance = cash

    def apply_trade(self, option_id: int, signed_qty: int, price: float) -> None:
        lock = signed_qty * price if signed_qty > 0 else (-signed_qty) * (1.0 - price)
        self.balance -= lock
        self.min_balance = min(self.min_balance, self.balance)
        self.n_fills += 1
        self.lots += abs(signed_qty)
        self.ledgers[option_id].append((signed_qty, price))

    def settle(self, option_id: int, payoff: float) -> None:
        for signed_qty, price in self.ledgers.pop(option_id, []):
            if signed_qty > 0:
                self.balance += signed_qty * payoff
            else:
                self.balance += (-signed_qty) * (1.0 - payoff)

    def end_of_day_check(self) -> None:
        if self.balance < 0:
            self.bankrupt = True


# --------------------------------------------------------------------- session

@dataclass
class SessionResult:
    pnl_by_name: dict[str, float]
    bankrupt_by_name: dict[str, bool]
    our_score: float
    our_fills: int = 0
    our_lots: int = 0
    our_min_balance: float = 0.0
    theo_rmse: float = 0.0


def _gen_history(params: MarketParameters, days: int, rng: random.Random) -> tuple[MarketHistory, dict[int, float]]:
    random.seed(rng.randrange(1 << 30))
    values = {FED: 2.0, AJR: rng.uniform(200.0, 1500.0), THR: rng.uniform(200.0, 2500.0)}
    hist: dict[int, list[float]] = {k: [v] for k, v in values.items()}
    for _ in range(days):
        values = params.advance_step(values)
        for k in hist:
            hist[k].append(values[k])
    return MarketHistory(values_by_underlying_id={k: tuple(v) for k, v in hist.items()}), values


class OptionFactory:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.next_id = 1000000

    def make(self, values: dict[int, float], n: int) -> list[BinaryOption]:
        out = []
        for _ in range(n):
            self.next_id += 1
            expiry = self.rng.choice([1, 1, 2, 2, 3, 5, 7, 10])
            kind = self.rng.random()
            if kind < 0.3:
                strike = round(round(values[FED] / 0.25) * 0.25 + self.rng.choice([-2, -1, 0, 0, 1, 2]) * 0.25, 2)
                legs = (OptionLeg(underlying_id=FED, weight=1.0),)
                strike = max(strike, 0.0)
            elif kind < 0.75:
                uid = self.rng.choice([AJR, THR])
                strike = round(values[uid] * self.rng.uniform(0.97, 1.03), 2)
                legs = (OptionLeg(underlying_id=uid, weight=1.0),)
            else:
                ratio = values[AJR] / max(values[THR], 1e-9)
                w = -round(ratio * self.rng.uniform(0.9, 1.1), 4)
                legs = (OptionLeg(underlying_id=AJR, weight=1.0), OptionLeg(underlying_id=THR, weight=w))
                strike = 0.0
            out.append(BinaryOption(legs=legs, option_id=self.next_id, steps_until_expiry=expiry, strike=strike))
        return out


def run_session(
    params: MarketParameters,
    flow_cfg: FlowConfig,
    opponents: list,
    capital: float,
    days: int,
    seed: int,
    mm_factory=None,
    fill_probe=None,
) -> SessionResult:
    rng = random.Random(seed)
    history, values = _gen_history(params, rng.randint(15, 60), rng)  # grader warm-ups are ~18 days
    true_model = _MarketModel.from_parameters(params)

    # Pre-generate the value path so sharp flow can peek one day ahead.
    random.seed(rng.randrange(1 << 30))
    path = [dict(values)]
    for _ in range(days + 1):
        path.append(params.advance_step(path[-1]))

    factory = OptionFactory(rng)
    active: list[BinaryOption] = factory.make(values, 12)

    def underlyings_of(vals: dict[int, float]) -> list[Underlying]:
        return [Underlying(name=n, underlying_id=uid, value=vals[uid])
                for uid, n in ((FED, "FED"), (AJR, "AJR"), (THR, "THR"))]

    ours = (mm_factory or (lambda u, o, c: MarketMaker(u, o, c)))(underlyings_of(values), list(active), capital)
    agents = [ours] + opponents
    accounts = {a.name: Account(capital) for a in agents}
    for agent in agents:
        agent.warm_up(history)
        agent.on_step_advance(underlyings_of(values), list(active))

    flow = FlowGenerator(flow_cfg, true_model, rng)

    for day in range(days):
        vals, next_vals = path[day], path[day + 1]
        live = [a for a in agents if not accounts[a.name].bankrupt]
        tradeable = [o for o in active if o.steps_until_expiry >= 1]
        if tradeable:
            for option, fok in flow.fok_orders(tradeable, vals, next_vals):
                acceptors = [a for a in live if _safe_fok(a, option, fok)]
                if not acceptors:
                    continue
                share = max(fok.quantity // len(acceptors), 1)
                for a in acceptors[: fok.quantity]:
                    q = min(share, fok.quantity)
                    signed = -q if fok.order_type is OrderType.BUY else q
                    accounts[a.name].apply_trade(option.option_id, signed, fok.price)
                    a.on_trade(option, fok.price, signed, fok.counterparty_id)
                    if fill_probe is not None:
                        fill_probe(a.name, "fok", option, signed, fok.price, dict(vals))
            for option, buy, qty, cp, _limit in flow.rfq_orders(tradeable, vals, next_vals):
                books = []
                for a in live:
                    q = _safe_quote(a, option, cp)
                    if q is not None:
                        books.append((a, q))
                if not books:
                    continue
                if buy:
                    books.sort(key=lambda t: t[1].offer_price)
                    remaining = qty
                    idx = 0
                    while remaining > 0 and idx < len(books):
                        level_price = books[idx][1].offer_price
                        level = [(a, q) for a, q in books[idx:] if q.offer_price == level_price]
                        share = max(remaining // len(level), 1)
                        for a, q in level:
                            if remaining <= 0:
                                break
                            fill = min(share, q.offer_quantity, remaining)
                            if fill > 0:
                                accounts[a.name].apply_trade(option.option_id, -fill, q.offer_price)
                                a.on_trade(option, q.offer_price, -fill, cp)
                                if fill_probe is not None:
                                    fill_probe(a.name, "rfq", option, -fill, q.offer_price, dict(vals))
                                remaining -= fill
                        idx += len(level)
                else:
                    books.sort(key=lambda t: -t[1].bid_price)
                    remaining = qty
                    idx = 0
                    while remaining > 0 and idx < len(books):
                        level_price = books[idx][1].bid_price
                        level = [(a, q) for a, q in books[idx:] if q.bid_price == level_price]
                        share = max(remaining // len(level), 1)
                        for a, q in level:
                            if remaining <= 0:
                                break
                            fill = min(share, q.bid_quantity, remaining)
                            if fill > 0:
                                accounts[a.name].apply_trade(option.option_id, fill, q.bid_price)
                                a.on_trade(option, q.bid_price, fill, cp)
                                if fill_probe is not None:
                                    fill_probe(a.name, "rfq", option, fill, q.bid_price, dict(vals))
                                remaining -= fill
                        idx += len(level)

        # Advance the day: decrement expiries, settle at the NEW values (grader convention).
        new_vals = next_vals
        advanced = [o.advance_step() for o in active]
        expired = [o for o in advanced if o.steps_until_expiry == 0]
        for option in expired:
            payoff = option.expiry_valuation(new_vals)
            for acct in accounts.values():
                acct.settle(option.option_id, payoff)
        active = [o for o in advanced if o.steps_until_expiry > 0] + factory.make(new_vals, rng.randint(2, 5))
        for acct in accounts.values():
            acct.end_of_day_check()
        for agent in agents:
            if not accounts[agent.name].bankrupt:
                agent.on_step_advance(underlyings_of(new_vals), list(active))

    pnl = {name: acct.balance - acct.start for name, acct in accounts.items()}
    bankrupt = {name: acct.bankrupt for name, acct in accounts.items()}
    our_name = ours.name
    if bankrupt[our_name]:
        score = 0.0
    else:
        others = [n for n in pnl if n != our_name]
        beaten = sum(1 for n in others if pnl[our_name] > pnl[n] or bankrupt[n])
        score = 0.4 + (0.6 * beaten / len(others) if others else 0.6)
    # Theo RMSE of the estimated model vs truth, over the final option set at final values.
    rmse = 0.0
    est = getattr(ours, "_model", None)
    if est is not None and active:
        vals_now = path[days]
        errs = [
            (_price_with_model(est, o, vals_now) - _price_with_model(true_model, o, vals_now)) ** 2
            for o in active
        ]
        rmse = (sum(errs) / len(errs)) ** 0.5
    acct = accounts[our_name]
    return SessionResult(
        pnl_by_name=pnl, bankrupt_by_name=bankrupt, our_score=score,
        our_fills=acct.n_fills, our_lots=acct.lots, our_min_balance=acct.min_balance,
        theo_rmse=rmse,
    )


def _safe_quote(agent, option, cp):
    try:
        return agent.quote(option, cp)
    except Exception:
        return None


def _safe_fok(agent, option, fok):
    try:
        return bool(agent.respond_to_fok(option, fok))
    except Exception:
        return False


# --------------------------------------------------------------------- archetypes & runner

def _params(rng: random.Random) -> MarketParameters:
    return MarketParameters(
        ajarai_drift=rng.uniform(-0.002, 0.003),
        ajarai_idio_std_dev=rng.uniform(0.008, 0.03),
        ajarai_rate_beta=rng.uniform(-0.1, -0.01),
        ajarai_sector_beta=rng.uniform(0.7, 1.3),
        rate_down_probability=rng.uniform(0.15, 0.3),
        rate_reversion_strength=rng.uniform(0.05, 0.15),
        rate_up_probability=rng.uniform(0.15, 0.3),
        sector_std_dev=rng.uniform(0.008, 0.025),
        theriodic_drift=rng.uniform(-0.002, 0.003),
        theriodic_idio_std_dev=rng.uniform(0.008, 0.03),
        theriodic_rate_beta=rng.uniform(-0.08, -0.01),
        theriodic_sector_beta=rng.uniform(0.6, 1.2),
    )


ARCHETYPES: dict[str, dict] = {
    "TC5_dumb_stalemate": dict(flow=FlowConfig("dumb", rfq_per_day=3, fok_per_day=2, qty_hi=12), capital=10.0,
                               opp=lambda p: [StalemateBot("Stalemate Quoter", p)]),
    "TC6_dumb_fw25": dict(flow=FlowConfig("dumb", rfq_per_day=3, fok_per_day=2, qty_hi=12), capital=10.0,
                          opp=lambda p: [FixedWidthBot("Fixed Width 0.25", p, 0.25), StalemateBot("Stalemate Quoter", p)]),
    "TC8_neutralish_fw10": dict(flow=FlowConfig("dumb", rfq_per_day=4, fok_per_day=2, qty_hi=12), capital=10.0,
                                opp=lambda p: [FixedWidthBot("Fixed Width 0.1", p, 0.10), StalemateBot("Stalemate Quoter", p)]),
    "TC11_tight_fw05": dict(flow=FlowConfig("neutral", rfq_per_day=4, fok_per_day=3, qty_hi=12), capital=20.0,
                            opp=lambda p: [FixedWidthBot("Fixed Width 0.05", p, 0.05), FixedWidthBot("Fixed Width 0.1", p, 0.10)]),
    "TC19_sharp": dict(flow=FlowConfig("sharp", rfq_per_day=4, fok_per_day=4, qty_hi=12), capital=40.0,
                       opp=lambda p: [FixedWidthBot("Fixed Width 0.05", p, 0.05), FixedWidthBot("Lattice", p, 0.16)]),
}


def main() -> None:
    MarketMaker.TELEMETRY = False
    n_seeds = 12
    days = 25
    print(f"{'archetype':<22} {'score':>6}  {'ourPnL':>8}  opponents (mean PnL)")
    overall = []
    for name, spec in ARCHETYPES.items():
        scores, our_pnls, opp_acc = [], [], defaultdict(list)
        for s in range(n_seeds):
            rng = random.Random(1000 + s)
            params = _params(rng)
            res = run_session(params, spec["flow"], spec["opp"](params), spec["capital"], days, seed=5000 + s)
            scores.append(res.our_score)
            for nm, v in res.pnl_by_name.items():
                if nm == "Hamza Khan":
                    our_pnls.append(v)
                else:
                    opp_acc[nm].append(v)
        opp_str = ", ".join(f"{nm}: {statistics.fmean(vs):+.2f}" for nm, vs in opp_acc.items())
        print(f"{name:<22} {statistics.fmean(scores):>6.3f}  {statistics.fmean(our_pnls):>+8.2f}  {opp_str}")
        overall.append(statistics.fmean(scores))
    print(f"\nmean archetype score: {statistics.fmean(overall):.3f}")


if __name__ == "__main__":
    main()
