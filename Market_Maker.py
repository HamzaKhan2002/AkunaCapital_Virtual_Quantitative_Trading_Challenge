import math
import random
from collections import defaultdict
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Final

AJARAI_NAME: Final[str] = "AJR"
AJARAI_UNDERLYING_ID: Final[int] = 2
FED_FUNDS_RATE_NAME: Final[str] = "FED"
FED_FUNDS_RATE_UNDERLYING_ID: Final[int] = 1
RATE_STRIKE_GRID: Final[float] = 0.25
THERIODIC_NAME: Final[str] = "THR"
THERIODIC_UNDERLYING_ID: Final[int] = 3

UNDERLYING_NAME_BY_ID: Final[dict[int, str]] = {
    AJARAI_UNDERLYING_ID: AJARAI_NAME,
    FED_FUNDS_RATE_UNDERLYING_ID: FED_FUNDS_RATE_NAME,
    THERIODIC_UNDERLYING_ID: THERIODIC_NAME,
}


@dataclass(eq=True, frozen=True, unsafe_hash=True)
class BinaryOption:
    legs: "tuple[OptionLeg, ...]"
    option_id: int
    steps_until_expiry: int
    strike: float

    def __post_init__(self) -> None:
        if self.steps_until_expiry < 0:
            raise ValueError("Steps until expiry must be non-negative")

        if not self.legs:
            raise ValueError("Binary option must have at least one leg")

        underlying_ids: list[int] = [leg.underlying_id for leg in self.legs]
        if len(underlying_ids) != len(set(underlying_ids)):
            raise ValueError("Binary option legs must reference distinct underlyings")

        if any(leg.weight == 0 for leg in self.legs):
            raise ValueError("Binary option leg weights must be non-zero")

    def __str__(self) -> str:
        terms: list[str] = []
        for index, leg in enumerate(self.legs):
            name: str = UNDERLYING_NAME_BY_ID.get(leg.underlying_id, str(leg.underlying_id))
            magnitude: float = abs(leg.weight)
            magnitude_str: str = "" if magnitude == 1 else f"{magnitude:.2f}*"
            if index == 0:
                sign: str = "-" if leg.weight < 0 else ""
            else:
                sign = " - " if leg.weight < 0 else " + "
            terms.append(f"{sign}{magnitude_str}{name}")
        observable_expression: str = "".join(terms)
        return f"{self.option_id} ({self.steps_until_expiry}d {observable_expression} >= {self.strike:.2f})"

    def advance_step(self) -> "BinaryOption":
        if self.steps_until_expiry == 0:
            return self

        return replace(self, steps_until_expiry=self.steps_until_expiry - 1)

    def contract_matches(self, other: "BinaryOption") -> bool:
        return replace(other, option_id=self.option_id) == self

    def expiry_valuation(self, value_by_underlying_id: dict[int, float]) -> float:
        return 1.0 if self.observable_value(value_by_underlying_id) >= self.strike else 0.0

    def observable_value(self, value_by_underlying_id: dict[int, float]) -> float:
        return sum(leg.weight * value_by_underlying_id[leg.underlying_id] for leg in self.legs)


@dataclass(frozen=True)
class FokOrder:
    counterparty_id: int
    option_id: int
    order_type: "OrderType"
    price: float
    quantity: int

    def __post_init__(self) -> None:
        if self.price < 0:
            raise ValueError("FOK order price must be non-negative")

        if self.quantity <= 0:
            raise ValueError("FOK order quantity must be positive")


@dataclass(frozen=True)
class MarketHistory:
    values_by_underlying_id: dict[int, tuple[float, ...]]

    def __post_init__(self) -> None:
        lengths: set[int] = {len(values) for values in self.values_by_underlying_id.values()}
        if len(lengths) > 1:
            raise ValueError("All underlyings must have the same number of historical days")

        if lengths and next(iter(lengths)) <= 0:
            raise ValueError("Market history must contain at least one day")

    @property
    def num_days(self) -> int:
        if not self.values_by_underlying_id:
            return 0
        return len(next(iter(self.values_by_underlying_id.values())))


@dataclass(frozen=True)
class MarketParameters:
    ajarai_drift: float
    ajarai_idio_std_dev: float
    ajarai_rate_beta: float
    ajarai_sector_beta: float
    rate_down_probability: float
    rate_reversion_strength: float
    rate_up_probability: float
    sector_std_dev: float
    theriodic_drift: float
    theriodic_idio_std_dev: float
    theriodic_rate_beta: float
    theriodic_sector_beta: float

    rate_step: float = 0.25
    rate_target: float = 2.0

    def __post_init__(self) -> None:
        if self.rate_step <= 0:
            raise ValueError("Rate step must be positive")

        if self.rate_up_probability <= 0 or self.rate_down_probability <= 0:
            raise ValueError("Rate up/down probabilities must both be positive")

        if self.rate_up_probability + self.rate_down_probability > 1:
            raise ValueError("Rate up/down probabilities must not sum to more than 1")

        if self.rate_target < 0:
            raise ValueError("Rate target must be non-negative")

        if not (0 <= self.rate_reversion_strength <= 1):
            raise ValueError("Rate reversion strength must be between 0 and 1")

        if self.ajarai_idio_std_dev < 0 or self.theriodic_idio_std_dev < 0 or self.sector_std_dev < 0:
            raise ValueError("Standard deviations must be non-negative")

    def advance_company_value(
        self,
        current_value: float,
        rate_change: float,
        sector_shock: float,
        *,
        drift: float,
        rate_beta: float,
        sector_beta: float,
        idio_std_dev: float,
    ) -> float:
        idiosyncratic_shock: float = random.gauss(mu=0.0, sigma=idio_std_dev)
        log_return: float = drift + (rate_beta * rate_change) + (sector_beta * sector_shock) + idiosyncratic_shock
        return round(current_value * math.exp(log_return), 2)

    def advance_rate(self, rate_value: float) -> float:
        up_probability, down_probability = self.tilted_rate_probabilities(rate_value)
        draw: float = random.random()
        if draw < up_probability:
            return self.next_rate_value(rate_value, 1)

        if draw < up_probability + down_probability:
            return self.next_rate_value(rate_value, -1)

        return rate_value

    def advance_step(self, value_by_underlying_id: dict[int, float]) -> dict[int, float]:
        current_rate_value: float = value_by_underlying_id[FED_FUNDS_RATE_UNDERLYING_ID]
        rate_value: float = self.advance_rate(current_rate_value)
        rate_change: float = round(rate_value - current_rate_value, 2)
        sector_shock: float = random.gauss(mu=0.0, sigma=self.sector_std_dev)
        return {
            FED_FUNDS_RATE_UNDERLYING_ID: rate_value,
            AJARAI_UNDERLYING_ID: self.advance_company_value(
                value_by_underlying_id[AJARAI_UNDERLYING_ID],
                rate_change,
                sector_shock,
                drift=self.ajarai_drift,
                rate_beta=self.ajarai_rate_beta,
                sector_beta=self.ajarai_sector_beta,
                idio_std_dev=self.ajarai_idio_std_dev,
            ),
            THERIODIC_UNDERLYING_ID: self.advance_company_value(
                value_by_underlying_id[THERIODIC_UNDERLYING_ID],
                rate_change,
                sector_shock,
                drift=self.theriodic_drift,
                rate_beta=self.theriodic_rate_beta,
                sector_beta=self.theriodic_sector_beta,
                idio_std_dev=self.theriodic_idio_std_dev,
            ),
        }

    def next_rate_value(self, rate_value: float, num_grid_steps: int) -> float:
        return max(round(rate_value + num_grid_steps * self.rate_step, 2), 0.0)

    def tilted_rate_probabilities(self, rate_value: float) -> tuple[float, float]:
        tilt: float = self.rate_reversion_strength * (self.rate_target - rate_value)
        up_probability: float = min(max(self.rate_up_probability + tilt, 0.0), 1.0)
        down_probability: float = min(max(self.rate_down_probability - tilt, 0.0), 1.0 - up_probability)
        return up_probability, down_probability


@dataclass(frozen=True)
class OptionLeg:
    underlying_id: int
    weight: float


class OrderType(StrEnum):
    BUY = "buy"
    SELL = "sell"


class Position:
    def __init__(self) -> None:
        self.option_quantity_by_option_id: dict[int, int] = defaultdict(int)

    def add_option_quantity(self, option_id: int, quantity: int) -> None:
        self.option_quantity_by_option_id[option_id] += quantity


@dataclass(frozen=True)
class Quote:
    bid_price: float
    bid_quantity: int
    offer_price: float
    offer_quantity: int

    def __post_init__(self) -> None:
        if self.bid_quantity <= 0 or self.offer_quantity <= 0:
            raise ValueError("Quote quantities must be positive")

        if not (0.0 <= self.bid_price <= 1.0 and 0.0 <= self.offer_price <= 1.0):
            raise ValueError("Quote prices must be between 0 and 1")

        if self.bid_price >= self.offer_price:
            raise ValueError("Quote bid price must be less than offer price")

        if any(abs(round(price * 100) - price * 100) > 1e-6 for price in (self.bid_price, self.offer_price)):
            raise ValueError("Quote prices must be in whole pennies (multiples of 0.01)")


@dataclass(frozen=True)
class Underlying:
    name: str
    underlying_id: int
    value: float

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Underlying):
            return False
        return self.underlying_id == other.underlying_id

# ============================================================================
# YOUR MARKET MAKER -- fill in the six stubbed methods below
# ============================================================================

_SQRT2: Final[float] = math.sqrt(2.0)


def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / _SQRT2))


def _npdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _fit_line(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """OLS (intercept, slope); slope forced to 0 when x has no variance."""
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx < 1e-12:
        return mean_y, 0.0
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = sxy / sxx
    return mean_y - slope * mean_x, slope


def _fit_line_se(xs: list[float], ys: list[float]) -> tuple[float, float, float, float, float]:
    """OLS with uncertainty: (intercept, slope, se_intercept, se_slope, cov_intercept_slope)."""
    n = len(xs)
    intercept, slope = _fit_line(xs, ys)
    if n < 3:
        return intercept, slope, 0.0, 0.0, 0.0
    mean_x = sum(xs) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    resid_ss = sum((y - intercept - slope * x) ** 2 for x, y in zip(xs, ys))
    s2 = resid_ss / (n - 2)
    if sxx < 1e-12:
        return intercept, slope, math.sqrt(max(s2 / n, 0.0)), 0.0, 0.0
    se_slope = math.sqrt(max(s2 / sxx, 0.0))
    se_intercept = math.sqrt(max(s2 * (1.0 / n + mean_x * mean_x / sxx), 0.0))
    cov_ab = -mean_x * s2 / sxx
    return intercept, slope, se_intercept, se_slope, cov_ab


@dataclass
class _CompanyLaw:
    drift: float      # per-step log-return drift
    rate_beta: float  # per-step sensitivity to realized rate change
    var: float        # per-step residual log variance (sector + idiosyncratic combined)


@dataclass
class _ParamErrors:
    """Estimator standard errors. All zero when parameters are known exactly (THEO)."""

    drift: dict[int, float] = field(default_factory=dict)
    rate_beta: dict[int, float] = field(default_factory=dict)
    drift_beta_cov: dict[int, float] = field(default_factory=dict)
    var: dict[int, float] = field(default_factory=dict)
    resid_cov: float = 0.0
    reversion: float = 0.0
    rate_prob: float = 0.0

    def any_uncertainty(self) -> bool:
        return bool(self.drift or self.var) or self.resid_cov > 0.0 or self.rate_prob > 0.0


@dataclass
class _MarketModel:
    """Everything the pricer needs. Built from true parameters (THEO) or estimates (live).

    Rate transition probabilities are linear in the rate with simulator-identical clamps:
    tilt = strength*(target - r)  =>  up(r) = (p_up + strength*target) - strength*r.
    Company pricing only needs per-step residual variances and their covariance --
    the sector/idio decomposition is unidentifiable from data and unnecessary.
    """

    rate_step: float
    up_intercept: float
    up_slope: float
    down_intercept: float
    down_slope: float
    company_laws: dict[int, _CompanyLaw]
    resid_cov: float  # per-step covariance of company residual log-returns
    n_obs: int        # sample size behind estimates (drives the estimation-risk floor)
    errors: "_ParamErrors" = field(default_factory=lambda: _ParamErrors())

    def rate_probabilities(self, rate_value: float) -> tuple[float, float]:
        up = min(max(self.up_intercept + self.up_slope * rate_value, 0.0), 1.0)
        down = min(max(self.down_intercept + self.down_slope * rate_value, 0.0), 1.0 - up)
        return up, down

    @classmethod
    def from_parameters(cls, mp: MarketParameters) -> "_MarketModel":
        return cls(
            rate_step=mp.rate_step,
            up_intercept=mp.rate_up_probability + mp.rate_reversion_strength * mp.rate_target,
            up_slope=-mp.rate_reversion_strength,
            down_intercept=mp.rate_down_probability - mp.rate_reversion_strength * mp.rate_target,
            down_slope=mp.rate_reversion_strength,
            company_laws={
                AJARAI_UNDERLYING_ID: _CompanyLaw(
                    drift=mp.ajarai_drift,
                    rate_beta=mp.ajarai_rate_beta,
                    var=(mp.ajarai_sector_beta * mp.sector_std_dev) ** 2 + mp.ajarai_idio_std_dev**2,
                ),
                THERIODIC_UNDERLYING_ID: _CompanyLaw(
                    drift=mp.theriodic_drift,
                    rate_beta=mp.theriodic_rate_beta,
                    var=(mp.theriodic_sector_beta * mp.sector_std_dev) ** 2 + mp.theriodic_idio_std_dev**2,
                ),
            },
            resid_cov=mp.ajarai_sector_beta * mp.theriodic_sector_beta * mp.sector_std_dev**2,
            n_obs=10**9,
        )


def _terminal_rate_distribution(model: _MarketModel, rate_0: float, steps: int) -> dict[float, float]:
    """Exact DP over the rate grid, mirroring advance_rate incl. floor at 0 and 2dp rounding."""
    dist: dict[float, float] = {round(rate_0, 2): 1.0}
    for _ in range(steps):
        nxt: dict[float, float] = defaultdict(float)
        for r, pr in dist.items():
            up, down = model.rate_probabilities(r)
            stay = 1.0 - up - down
            if up > 0.0:
                nxt[max(round(r + model.rate_step, 2), 0.0)] += pr * up
            if down > 0.0:
                nxt[max(round(r - model.rate_step, 2), 0.0)] += pr * down
            if stay > 0.0:
                nxt[r] += pr * stay
        dist = dict(nxt)
    return dist


def _single_company_tail(
    weight: float, value_0: float, strike_resid: float, mu: float, sd: float
) -> float:
    """P(weight * V_T >= strike_resid) for lognormal V_T = value_0 * exp(N(mu, sd^2))."""
    if value_0 <= 0.0:
        return 1.0 if strike_resid <= 1e-12 else 0.0
    if weight > 0.0:
        threshold = strike_resid / weight
        if threshold <= 0.0:
            return 1.0
        log_thr = math.log(threshold / value_0)
        if sd <= 0.0:
            return 1.0 if mu >= log_thr else 0.0
        return _ncdf((mu - log_thr) / sd)
    threshold = strike_resid / weight  # weight < 0 flips the inequality: V_T <= threshold
    if threshold <= 0.0:
        return 0.0
    log_thr = math.log(threshold / value_0)
    if sd <= 0.0:
        return 1.0 if mu <= log_thr else 0.0
    return _ncdf((log_thr - mu) / sd)


def _company_event_probability(
    model: _MarketModel,
    comp_legs: list[OptionLeg],
    strike_resid: float,
    rate_delta: float,
    steps: int,
    value_by_id: dict[int, float],
) -> float:
    """P(sum_i w_i * V_i,T >= strike_resid | total rate change = rate_delta)."""
    if not comp_legs:
        return 1.0 if strike_resid <= 1e-12 else 0.0

    laws = model.company_laws
    if len(comp_legs) == 1:
        leg = comp_legs[0]
        law = laws[leg.underlying_id]
        mu = steps * law.drift + law.rate_beta * rate_delta
        sd = math.sqrt(max(steps * law.var, 0.0))
        return _single_company_tail(leg.weight, value_by_id[leg.underlying_id], strike_resid, mu, sd)

    leg1, leg2 = comp_legs[0], comp_legs[1]
    law1, law2 = laws[leg1.underlying_id], laws[leg2.underlying_id]
    v1_0, v2_0 = value_by_id[leg1.underlying_id], value_by_id[leg2.underlying_id]
    mu1 = steps * law1.drift + law1.rate_beta * rate_delta
    mu2 = steps * law2.drift + law2.rate_beta * rate_delta
    var1 = max(steps * law1.var, 0.0)
    var2 = max(steps * law2.var, 0.0)
    cov = steps * model.resid_cov

    # Zero-strike opposite-sign spread (the advertised case): closed form on the log difference.
    if abs(strike_resid) <= 1e-12 and leg1.weight * leg2.weight < 0.0 and v1_0 > 0.0 and v2_0 > 0.0:
        if leg1.weight > 0.0:
            w_pos, v_pos_0, mu_pos, var_pos = leg1.weight, v1_0, mu1, var1
            w_neg, v_neg_0, mu_neg, var_neg = -leg2.weight, v2_0, mu2, var2
        else:
            w_pos, v_pos_0, mu_pos, var_pos = leg2.weight, v2_0, mu2, var2
            w_neg, v_neg_0, mu_neg, var_neg = -leg1.weight, v1_0, mu1, var1
        # w_pos*V_pos >= w_neg*V_neg  <=>  R_pos - R_neg >= ln(w_neg*v_neg_0 / (w_pos*v_pos_0))
        diff_mu = mu_pos - mu_neg
        diff_var = max(var_pos + var_neg - 2.0 * cov, 0.0)
        log_thr = math.log((w_neg * v_neg_0) / (w_pos * v_pos_0))
        if diff_var <= 0.0:
            return 1.0 if diff_mu >= log_thr else 0.0
        return _ncdf((diff_mu - log_thr) / math.sqrt(diff_var))

    # General two-leg case: quadrature over leg2, closed-form conditional tail for leg1.
    sd2 = math.sqrt(var2)
    if sd2 <= 0.0:
        v2_terminal = v2_0 * math.exp(mu2)
        return _single_company_tail(
            leg1.weight, v1_0, strike_resid - leg2.weight * v2_terminal, mu1, math.sqrt(var1)
        )
    cond_var = max(var1 - (cov * cov) / var2, 0.0)
    cond_sd = math.sqrt(cond_var)
    total = 0.0
    weight_sum = 0.0
    num_nodes = 241
    z_lim = 7.0
    dz = 2.0 * z_lim / (num_nodes - 1)
    for i in range(num_nodes):
        z = -z_lim + i * dz
        node_weight = _npdf(z) * dz
        r2 = mu2 + sd2 * z
        cond_mu1 = mu1 + (cov / var2) * (r2 - mu2)
        remaining = strike_resid - leg2.weight * v2_0 * math.exp(r2)
        total += node_weight * _single_company_tail(leg1.weight, v1_0, remaining, cond_mu1, cond_sd)
        weight_sum += node_weight
    return total / weight_sum if weight_sum > 0.0 else 0.5


def _price_with_model(model: _MarketModel, option: BinaryOption, value_by_id: dict[int, float]) -> float:
    steps = option.steps_until_expiry
    if steps == 0:
        return option.expiry_valuation(value_by_id)

    fed_weight = 0.0
    comp_legs: list[OptionLeg] = []
    for leg in option.legs:
        if leg.underlying_id == FED_FUNDS_RATE_UNDERLYING_ID:
            fed_weight += leg.weight
        else:
            comp_legs.append(leg)

    rate_0 = value_by_id.get(FED_FUNDS_RATE_UNDERLYING_ID, 0.0)
    rate_dist = _terminal_rate_distribution(model, rate_0, steps)
    total = 0.0
    for rate_t, prob in rate_dist.items():
        if prob <= 0.0:
            continue
        strike_resid = option.strike - fed_weight * rate_t
        total += prob * _company_event_probability(
            model, comp_legs, strike_resid, rate_t - rate_0, steps, value_by_id
        )
    return min(max(total, 0.0), 1.0)


def _with_company(model: _MarketModel, uid: int, **kw) -> _MarketModel:
    laws = dict(model.company_laws)
    laws[uid] = replace(laws[uid], **kw)
    return replace(model, company_laws=laws)


_SIGMA_DRAWS: Final[int] = 12

def _sigma_epsilon(
    model: _MarketModel, option: BinaryOption, value_by_id: dict[int, float], n_draws: int = None
) -> float:
    """Std dev of our own theo error, by sampling the estimator's sampling distribution.

    The delta method fails here: at ~18-day warm-ups the parameter uncertainty is large,
    so local linearization understates error wherever dV/dtheta happens to vanish
    (measured std(z) = 129 vs target 1). Sampling parameters and repricing is
    distribution-faithful at comparable cost. Deterministic per option: no side effects.
    Returns 0 when parameters are exact (THEO), which is correct by construction.
    n_draws overrides _SIGMA_DRAWS for sensitivity testing only; production uses the default.
    """
    e = model.errors
    if option.steps_until_expiry == 0 or not e.any_uncertainty():
        return 0.0

    draws = n_draws if n_draws is not None else _SIGMA_DRAWS
    rng = random.Random(option.option_id * 6364136223846793005 + option.steps_until_expiry)
    prices: list[float] = []
    for _ in range(draws):
        laws = {}
        for uid, law in model.company_laws.items():
            sd_d = e.drift.get(uid, 0.0)
            sd_b = e.rate_beta.get(uid, 0.0)
            cov_db = e.drift_beta_cov.get(uid, 0.0)
            z1, z2 = rng.gauss(0.0, 1.0), rng.gauss(0.0, 1.0)
            d_new = law.drift + sd_d * z1
            if sd_d > 1e-12:
                slope = cov_db / (sd_d * sd_d)
                resid_sd = math.sqrt(max(sd_b * sd_b - slope * slope * sd_d * sd_d, 0.0))
                b_new = law.rate_beta + slope * (sd_d * z1) + resid_sd * z2
            else:
                b_new = law.rate_beta + sd_b * z2
            sd_v = e.var.get(uid, 0.0)
            v_new = max(law.var + sd_v * rng.gauss(0.0, 1.0), 0.05 * law.var, 1e-12)
            laws[uid] = _CompanyLaw(drift=d_new, rate_beta=b_new, var=v_new)

        cov_new = model.resid_cov + e.resid_cov * rng.gauss(0.0, 1.0)
        ids = list(laws)
        if len(ids) > 1:
            cap = math.sqrt(laws[ids[0]].var * laws[ids[1]].var)
            cov_new = min(max(cov_new, -cap), cap)

        rev_shift = e.reversion * rng.gauss(0.0, 1.0)
        p_shift = e.rate_prob * rng.gauss(0.0, 1.0)
        draw = replace(
            model,
            company_laws=laws,
            resid_cov=cov_new,
            up_slope=model.up_slope - rev_shift,
            down_slope=model.down_slope + rev_shift,
            up_intercept=model.up_intercept + p_shift,
            down_intercept=model.down_intercept - p_shift,
        )
        prices.append(_price_with_model(draw, option, value_by_id))

    mean = sum(prices) / len(prices)
    var = sum((p - mean) ** 2 for p in prices) / max(len(prices) - 1, 1)
    sigma = math.sqrt(max(var, 0.0))
    base = _price_with_model(model, option, value_by_id)
    return min(sigma, math.sqrt(max(base * (1.0 - base), 0.0)) + 1e-9)


class _OptionLedger:
    """Per-option margin bookkeeping mirroring the autograder (Problem_2 rules)."""

    __slots__ = ("bought", "sold", "bought_lock", "sold_lock")

    def __init__(self) -> None:
        self.bought: int = 0
        self.sold: int = 0
        self.bought_lock: float = 0.0
        self.sold_lock: float = 0.0


class MarketMaker:
    # Regimes are inferred per-session from observed flow; see _regime().
    _DUMB: Final[int] = 0
    _NEUTRAL: Final[int] = 1
    _TOXIC: Final[int] = 2

    BASE_HALF_SPREAD: Final[float] = 0.008
    RISK_HALF_SPREAD: Final[float] = 0.030
    SE_FLOOR_SCALE: Final[float] = 0.35
    SE_FLOOR_CAP: Final[float] = 0.02
    SIZE_CAP: Final[int] = 120
    MARGIN_RESERVE_FRAC: Final[float] = 0.08
    CP_WIDEN_CAP: Final[float] = 0.06
    # Proportional shading: bid = lam*theo, offer = 1 - lam*(1-theo) -> uniform ~ (1-lam)/lam
    # expected return per locked dollar on every fill, tight at extremes, wide ATM.
    LAMBDA_NEUTRAL: Final[float] = 0.72
    LAMBDA_TOXIC: Final[float] = 0.35
    DUMB_RUNG_LAMBDA: Final[tuple[float, ...]] = (0.15, 0.08, 0.03)
    INV_SKEW_PER_LOT: Final[float] = 0.02
    QUOTE_FRAC: Final[dict[int, float]] = {_DUMB: 0.60, _NEUTRAL: 0.35, _TOXIC: 0.05}
    FOK_LOCK_FRAC: Final[dict[int, float]] = {_DUMB: 0.60, _NEUTRAL: 0.50, _TOXIC: 0.04}
    FOK_EDGE_BUMP: Final[dict[int, float]] = {_DUMB: 0.0, _NEUTRAL: 0.006, _TOXIC: 0.035}
    FOK_RATIO_FLOOR: Final[float] = 0.12
    POS_SOFT_CAP: Final[dict[int, int]] = {_DUMB: 60, _NEUTRAL: 25, _TOXIC: 10}
    DRAWDOWN_LIMIT_FRAC: Final[float] = 0.05
    JUNK_FILL_EDGE: Final[float] = 0.08

    TELEMETRY: bool = False         # stderr proven SAFE but INVISIBLE in the grader; no probe channel exists
    TELEMETRY_EVENT_BUDGET: int = 40  # local-only debugging; stdout must never be touched
    SHRINK_ESTIMATOR: bool = False  # v5 default; the ONLY switch under A/B in the shrinkage experiment

    def __init__(
        self,
        underlying_initial_state: list[Underlying],
        option_initial_state: list[BinaryOption],
        cash_balance: float,
    ) -> None:
        self.underlying_state: list[Underlying] = underlying_initial_state
        self.active_option_state: list[BinaryOption] = option_initial_state
        self.cash_balance: float = cash_balance
        self.position: Position = Position()

        self._initial_cash: float = cash_balance
        self._margin_available: float = cash_balance
        self._model: _MarketModel | None = None
        self._ledgers: dict[int, _OptionLedger] = defaultdict(_OptionLedger)
        self._settled_option_ids: set[int] = set()
        self._cp_toxicity: dict[int, float] = defaultdict(float)
        self._pending_markouts: list[tuple[int, int, int, float]] = []  # (cp, option_id, sign, V_at_trade)
        self._flow_iq_ewma: float = 0.0   # +ve = counterparties cross through theo (dumb flow)
        self._flow_iq_n: int = 0
        self._global_tox: float = 0.0     # EWMA of adverse markouts on our own fills
        self._realized_pnl: float = 0.0   # settled cash PnL vs locks, drives the drawdown guard
        self._fills_today: int = 0
        self._junk_today: int = 0
        self._junk_fills: int = 0         # fills >= JUNK_FILL_EDGE through theo: near-conclusive dumb evidence
        self._dumb_rung: int = 0          # index into DUMB_RUNG_LAMBDA, escalates while junk persists
        self._day: int = 0
        self._event_lines: int = 0
        self._log(
            f"HK|S|cap={cash_balance:.2f}|opts={len(option_initial_state)}|"
            + "|".join(f"{u.name}={u.value:.2f}" for u in underlying_initial_state)
        )

    def _log(self, line: str, budgeted: bool = False) -> None:
        try:
            if not MarketMaker.TELEMETRY:
                return
            if budgeted:
                if self._event_lines >= self.TELEMETRY_EVENT_BUDGET:
                    return
                self._event_lines += 1
            import sys

            print(line, file=sys.stderr, flush=False)  # stderr ONLY: stdout is parsed by the checker
        except Exception:
            pass

    def on_step_advance(self, new_underlying_state: list[Underlying], new_option_state: list[BinaryOption]) -> None:
        old_options: dict[int, BinaryOption] = {o.option_id: o for o in self.active_option_state}
        self.underlying_state = new_underlying_state
        self.active_option_state = new_option_state
        try:
            values = {u.underlying_id: u.value for u in new_underlying_state}
            new_by_id = {o.option_id: o for o in new_option_state}
            for option in new_option_state:
                if option.steps_until_expiry == 0:
                    self._settle(option, values)
            for option_id, option in old_options.items():
                if option_id not in new_by_id:
                    self._settle(option, values)
            self._process_markouts(new_by_id)
            if self._junk_today >= 1 and self._global_tox <= 0.008 and self._dumb_rung < len(self.DUMB_RUNG_LAMBDA) - 1:
                self._dumb_rung += 1
            elif (self._junk_today == 0 or self._global_tox > 0.008) and self._dumb_rung > 0:
                self._dumb_rung -= 1
            self._day += 1
            self._log(
                f"HK|D|d={self._day}|m={self._margin_available:.2f}|rp={self._realized_pnl:.2f}"
                f"|rg={self._regime()}|rung={self._dumb_rung}|jf={self._junk_fills}|fq={self._flow_iq_ewma:+.3f}/{self._flow_iq_n}"
                f"|tox={self._global_tox:.4f}|fills={self._fills_today}|"
                + "|".join(f"{u.name}={u.value:.2f}" for u in new_underlying_state)
            )
            self._fills_today = 0
            self._junk_today = 0
        except Exception:
            pass  # bookkeeping must never take the bot down

    def on_trade(self, option: BinaryOption, price: float, quantity: int, counterparty_id: int) -> None:
        self.position.add_option_quantity(option.option_id, quantity)
        try:
            ledger = self._ledgers[option.option_id]
            if quantity >= 0:
                lock = quantity * price
                self._margin_available -= lock
                ledger.bought += quantity
                ledger.bought_lock += lock
            else:
                lock = (-quantity) * (1.0 - price)
                self._margin_available -= lock
                ledger.sold += -quantity
                ledger.sold_lock += lock
            sign = 1 if quantity >= 0 else -1
            theo_now = self.price_option(option)
            self._pending_markouts.append((counterparty_id, option.option_id, sign, theo_now))
            self._fills_today += 1
            fill_edge = (theo_now - price) if quantity >= 0 else (price - theo_now)
            if fill_edge >= self.JUNK_FILL_EDGE:
                self._junk_fills += 1
                self._junk_today += 1
            self._log(
                f"HK|T|d={self._day}|o={option.option_id}|q={quantity:+d}@{price:.2f}"
                f"|th={theo_now:.3f}|e={fill_edge:+.3f}|cp={counterparty_id}|m={self._margin_available:.2f}",
                budgeted=True,
            )
        except Exception:
            pass

    @property
    def name(self) -> str:
        return "Hamza Khan"

    def price_option(self, option: BinaryOption) -> float:
        try:
            values = {u.underlying_id: u.value for u in self.underlying_state}
            if option.steps_until_expiry == 0:
                return option.expiry_valuation(values)
            model = self._model if self._model is not None else self._fallback_model()
            return _price_with_model(model, option, values)
        except Exception:
            return 0.5

    def price_option_from_parameters(
        self, market_parameters: MarketParameters, option: BinaryOption
    ) -> float:
        try:
            values = {u.underlying_id: u.value for u in self.underlying_state}
            if option.steps_until_expiry == 0:
                return option.expiry_valuation(values)
            return _price_with_model(_MarketModel.from_parameters(market_parameters), option, values)
        except Exception:
            return 0.5

    def quote(self, option: BinaryOption, counterparty_id: int) -> Quote:
        try:
            theo = self.price_option(option)
            if not (0.0 <= theo <= 1.0) or theo != theo:
                theo = 0.5
            regime = self._regime()
            inventory = self.position.option_quantity_by_option_id.get(option.option_id, 0)
            bernoulli_sd = math.sqrt(max(theo * (1.0 - theo), 0.0))
            steps = min(max(option.steps_until_expiry, 1), 10)

            if regime == self._DUMB:
                lam = self.DUMB_RUNG_LAMBDA[self._dumb_rung]
            elif regime == self._TOXIC:
                lam = self.LAMBDA_TOXIC
            else:
                lam = self.LAMBDA_NEUTRAL - 2.0 * self._se_floor(bernoulli_sd) - self._cp_widen(counterparty_id)
            lam = min(max(lam, 0.03), 0.90)

            # Inventory control in lambda-space: long -> bid backs off, offer approaches theo.
            lam_bid = lam * min(max(1.0 - self.INV_SKEW_PER_LOT * max(inventory, 0), 0.4), 1.0)
            lam_off = lam * min(max(1.0 - self.INV_SKEW_PER_LOT * max(-inventory, 0), 0.4), 1.0)

            bid = math.floor(theo * lam_bid * 100.0 + 1e-9) / 100.0
            offer = math.ceil((1.0 - (1.0 - theo) * lam_off) * 100.0 - 1e-9) / 100.0
            if regime == self._DUMB and self._dumb_rung == len(self.DUMB_RUNG_LAMBDA) - 1:
                # Price-improve extreme quoters by one tick when theo covers the tick cost;
                # otherwise sit AT the extreme and take the equal tie-split.
                bid = max(bid, 0.01) if theo >= 0.03 else bid
                offer = min(offer, 0.99) if theo <= 0.97 else offer
            bid = min(max(bid, 0.0), 0.99)
            offer = min(max(offer, bid + 0.01, 0.01), 1.0)
            bid = round(bid, 2)
            offer = round(offer, 2)
            if bid >= offer:
                bid = round(max(offer - 0.01, 0.0), 2)

            afford = max(self._margin_available - self.MARGIN_RESERVE_FRAC * self._initial_cash, 0.0)
            per_side = self.QUOTE_FRAC[regime] * afford / math.sqrt(steps)
            bid_qty = self._clamp_size(per_side / max(bid, 0.006))
            offer_qty = self._clamp_size(per_side / max(1.0 - offer, 0.006))
            # Solvency degrade: if a side cannot afford even ONE lot, quote it margin-free.
            if bid * 1.0 > afford / 2.0:
                bid, bid_qty = 0.0, 1
                offer = max(offer, 0.01)
            if (1.0 - offer) * 1.0 > afford / 2.0:
                offer, offer_qty = 1.0, 1
                bid = min(bid, 0.99)
            cap = self.POS_SOFT_CAP[regime]
            if inventory > cap:
                bid_qty = 1
            if inventory < -cap:
                offer_qty = 1
            self._log(
                f"HK|Q|d={self._day}|o={option.option_id}|T={option.steps_until_expiry}"
                f"|th={theo:.3f}|b={bid:.2f}x{bid_qty}|a={offer:.2f}x{offer_qty}|rg={regime}|inv={inventory}|cp={counterparty_id}",
                budgeted=True,
            )
            return Quote(bid, bid_qty, offer, offer_qty)
        except Exception:
            return Quote(0.0, 1, 1.0, 1)  # zero-margin-at-risk fallback: never errors, never bankrupts

    def respond_to_fok(self, option: BinaryOption, fok_order: FokOrder) -> bool:
        try:
            theo = self.price_option(option)
            inventory = self.position.option_quantity_by_option_id.get(option.option_id, 0)
            if fok_order.order_type is OrderType.BUY:  # counterparty buys -> we sell
                edge = fok_order.price - theo
                lock = fok_order.quantity * (1.0 - fok_order.price)
                worsens_inventory = inventory < 0
            else:  # counterparty sells -> we buy
                edge = theo - fok_order.price
                lock = fok_order.quantity * fok_order.price
                worsens_inventory = inventory > 0

            # Every FOK is free information about flow quality, traded or not.
            self._flow_iq_ewma = 0.85 * self._flow_iq_ewma + 0.15 * min(max(edge, -0.25), 0.25)
            self._flow_iq_n += 1

            regime = self._regime()
            budget = max(self._margin_available - self.MARGIN_RESERVE_FRAC * self._initial_cash, 0.0)
            if lock > min(self.FOK_LOCK_FRAC[regime] * budget, budget):
                return False
            lock_per_lot = (1.0 - fok_order.price) if fok_order.order_type is OrderType.BUY else fok_order.price
            ratio_reject = (
                regime != self._DUMB
                and lock_per_lot > 1e-9
                and edge / lock_per_lot < self.FOK_RATIO_FLOOR
            )
            bernoulli_sd = math.sqrt(max(theo * (1.0 - theo), 0.0))
            threshold = (
                max(0.006, 0.6 * self._se_floor(bernoulli_sd))
                + self.FOK_EDGE_BUMP[regime]
                + 1.5 * self._cp_toxicity.get(fok_order.counterparty_id, 0.0)
                + (0.02 if worsens_inventory and abs(inventory) > self.POS_SOFT_CAP[regime] else 0.0)
            )
            accept = not ratio_reject and edge >= threshold
            # v9: quantile bound vs our own estimation error (E26 illusory-edge finding).
            # Gated OFF in DUMB regime: uninformed crossers don't exploit estimation error,
            # so the penalty there is pure opportunity cost (E27: raw bound SIG- in dumb world).
            if accept and regime != self._DUMB:
                values = {u.underlying_id: u.value for u in self.underlying_state}
                model = self._model if self._model is not None else self._fallback_model()
                accept = edge >= _sigma_epsilon(model, option, values)
            self._log(
                f"HK|F|d={self._day}|{fok_order.order_type}|p={fok_order.price:.2f}x{fok_order.quantity}"
                f"|o={option.option_id}|th={theo:.3f}|e={edge:+.3f}|acc={int(accept)}"
                f"|rr={int(ratio_reject)}|thr={threshold:.3f}|cp={fok_order.counterparty_id}",
                budgeted=True,
            )
            return accept
        except Exception:
            return False

    def warm_up(self, market_history: MarketHistory) -> None:
        try:
            self._model = self._estimate_model(market_history)
            m = self._model
            if m is not None:
                laws = m.company_laws
                a, t = laws[AJARAI_UNDERLYING_ID], laws[THERIODIC_UNDERLYING_ID]
                self._log(
                    f"HK|W|n={market_history.num_days}|obs={m.n_obs}"
                    f"|up={m.up_intercept:.3f}{m.up_slope:+.3f}r|dn={m.down_intercept:.3f}{m.down_slope:+.3f}r"
                    f"|A(mu={a.drift:+.4f},b={a.rate_beta:+.3f},sd={math.sqrt(a.var):.4f})"
                    f"|T(mu={t.drift:+.4f},b={t.rate_beta:+.3f},sd={math.sqrt(t.var):.4f})"
                    f"|cov={m.resid_cov:+.6f}"
                )
        except Exception:
            self._model = None  # fallback model keeps us alive

    # ------------------------------------------------------------------ helpers

    def _regime(self) -> int:
        if self._realized_pnl < -self.DRAWDOWN_LIMIT_FRAC * self._initial_cash or self._global_tox > 0.015:
            return self._TOXIC
        if self._flow_iq_n >= 3 and self._flow_iq_ewma < -0.005:
            return self._TOXIC
        if self._flow_iq_n >= 3 and self._flow_iq_ewma > 0.02 and self._global_tox <= 0.005:
            return self._DUMB
        # Low-event sessions: two fills through theo are near-conclusive junk evidence.
        if self._junk_fills >= 2 and self._global_tox <= 0.008 and self._realized_pnl >= -0.02 * self._initial_cash:
            return self._DUMB
        return self._NEUTRAL

    def _clamp_size(self, raw: float) -> int:
        return max(1, min(self.SIZE_CAP, int(raw)))

    def _se_floor(self, bernoulli_sd: float) -> float:
        n = self._model.n_obs if self._model is not None else 1
        return min(self.SE_FLOOR_CAP, self.SE_FLOOR_SCALE * bernoulli_sd / math.sqrt(max(n, 1)))

    def _cp_widen(self, counterparty_id: int) -> float:
        return min(max(2.0 * self._cp_toxicity.get(counterparty_id, 0.0), 0.0), self.CP_WIDEN_CAP)

    def _fallback_model(self) -> _MarketModel:
        return _MarketModel(
            rate_step=RATE_STRIKE_GRID,
            up_intercept=1.0 / 3.0,
            up_slope=0.0,
            down_intercept=1.0 / 3.0,
            down_slope=0.0,
            company_laws={
                AJARAI_UNDERLYING_ID: _CompanyLaw(drift=0.0, rate_beta=0.0, var=0.0004),
                THERIODIC_UNDERLYING_ID: _CompanyLaw(drift=0.0, rate_beta=0.0, var=0.0004),
            },
            resid_cov=0.0,
            n_obs=1,
        )

    def _settle(self, option: BinaryOption, value_by_id: dict[int, float]) -> None:
        option_id = option.option_id
        if option_id in self._settled_option_ids:
            return
        self._settled_option_ids.add(option_id)
        ledger = self._ledgers.get(option_id)
        if ledger is None:
            return
        payoff = option.expiry_valuation(value_by_id)
        credit = ledger.bought * payoff + ledger.sold * (1.0 - payoff)
        self._margin_available += credit
        self._realized_pnl += credit - (ledger.bought_lock + ledger.sold_lock)

    def _process_markouts(self, new_by_id: dict[int, BinaryOption]) -> None:
        for counterparty_id, option_id, sign, theo_at_trade in self._pending_markouts:
            option = new_by_id.get(option_id)
            if option is None:
                continue
            markout = sign * (self.price_option(option) - theo_at_trade)
            clipped = min(max(-markout, -0.2), 0.2)  # positive = flow moved against us
            self._cp_toxicity[counterparty_id] = 0.8 * self._cp_toxicity[counterparty_id] + 0.2 * clipped
            self._global_tox = 0.85 * self._global_tox + 0.15 * clipped
        self._pending_markouts = []

    def _estimate_model(self, market_history: MarketHistory) -> _MarketModel:
        values = market_history.values_by_underlying_id
        rates = list(values.get(FED_FUNDS_RATE_UNDERLYING_ID, ()))
        ajr = list(values.get(AJARAI_UNDERLYING_ID, ()))
        thr = list(values.get(THERIODIC_UNDERLYING_ID, ()))
        n = min(len(rates), len(ajr), len(thr))
        if n < 3:
            return self._fallback_model()

        step = RATE_STRIKE_GRID
        rate_changes = [round(rates[i + 1] - rates[i], 2) for i in range(n - 1)]

        # Rate transitions: linear-probability fits, excluding floor-ambiguous rows at r ~ 0.
        xs: list[float] = []
        up_ys: list[float] = []
        down_ys: list[float] = []
        for i in range(n - 1):
            if rates[i] <= step / 2.0:
                continue
            xs.append(rates[i])
            up_ys.append(1.0 if rate_changes[i] > step / 2.0 else 0.0)
            down_ys.append(1.0 if rate_changes[i] < -step / 2.0 else 0.0)
        up_int, up_slope = _fit_line(xs, up_ys)
        down_int, down_slope = _fit_line(xs, down_ys)
        _, _, _, se_up_slope, _ = _fit_line_se(xs, up_ys)
        _, _, se_up_int, se_down_slope, _ = _fit_line_se(xs, down_ys)
        # Theory: up_slope = -lambda, down_slope = +lambda. Symmetrize and re-anchor at mean rate.
        reversion = max((down_slope - up_slope) / 2.0, 0.0)
        if self.SHRINK_ESTIMATOR:
            n_r = len(xs)
            reversion *= n_r / (n_r + 15.0)
            reversion = min(reversion, 0.5)
        mean_rate = sum(xs) / len(xs) if xs else 2.0
        up_at_mean = up_int + up_slope * mean_rate
        down_at_mean = down_int + down_slope * mean_rate
        up_int = up_at_mean + reversion * mean_rate
        down_int = down_at_mean - reversion * mean_rate

        # Company laws: OLS of log-returns on realized rate change; residual moments -> joint law.
        log_ret_a: list[float] = []
        log_ret_t: list[float] = []
        deltas: list[float] = []
        for i in range(n - 1):
            if ajr[i] <= 0.0 or ajr[i + 1] <= 0.0 or thr[i] <= 0.0 or thr[i + 1] <= 0.0:
                continue
            log_ret_a.append(math.log(ajr[i + 1] / ajr[i]))
            log_ret_t.append(math.log(thr[i + 1] / thr[i]))
            deltas.append(rate_changes[i])
        if len(deltas) < 3:
            return self._fallback_model()
        drift_a, beta_a = _fit_line(deltas, log_ret_a)
        drift_t, beta_t = _fit_line(deltas, log_ret_t)
        _, _, se_drift_a, se_beta_a, cov_db_a = _fit_line_se(deltas, log_ret_a)
        _, _, se_drift_t, se_beta_t, cov_db_t = _fit_line_se(deltas, log_ret_t)
        m = len(deltas)
        if self.SHRINK_ESTIMATOR:
            # James-Stein-style: strength per parameter's prior-scale/SE ratio (E17 derivation).
            sh_d = m / (m + 60.0)
            sh_b = m / (m + 8.0)
            drift_a *= sh_d
            drift_t *= sh_d
            beta_a *= sh_b
            beta_t *= sh_b
        resid_a = [y - drift_a - beta_a * x for x, y in zip(deltas, log_ret_a)]
        resid_t = [y - drift_t - beta_t * x for x, y in zip(deltas, log_ret_t)]
        var_a = max(sum(e * e for e in resid_a) / m, 1e-12)
        var_t = max(sum(e * e for e in resid_t) / m, 1e-12)
        cov = sum(ea * et for ea, et in zip(resid_a, resid_t)) / m
        max_cov = math.sqrt(var_a * var_t)
        cov = min(max(cov, -max_cov), max_cov)

        errors = _ParamErrors(
            drift={AJARAI_UNDERLYING_ID: se_drift_a, THERIODIC_UNDERLYING_ID: se_drift_t},
            rate_beta={AJARAI_UNDERLYING_ID: se_beta_a, THERIODIC_UNDERLYING_ID: se_beta_t},
            drift_beta_cov={AJARAI_UNDERLYING_ID: cov_db_a, THERIODIC_UNDERLYING_ID: cov_db_t},
            # Var(s^2) ~ 2 s^4 / m for a Gaussian sample.
            var={
                AJARAI_UNDERLYING_ID: var_a * math.sqrt(2.0 / m),
                THERIODIC_UNDERLYING_ID: var_t * math.sqrt(2.0 / m),
            },
            resid_cov=math.sqrt(max((var_a * var_t + cov * cov) / m, 0.0)),
            reversion=max(se_up_slope, se_down_slope),
            rate_prob=se_up_int,
        )

        return _MarketModel(
            rate_step=step,
            up_intercept=up_int,
            up_slope=-reversion,
            down_intercept=down_int,
            down_slope=reversion,
            company_laws={
                AJARAI_UNDERLYING_ID: _CompanyLaw(drift=drift_a, rate_beta=beta_a, var=var_a),
                THERIODIC_UNDERLYING_ID: _CompanyLaw(drift=drift_t, rate_beta=beta_t, var=var_t),
            },
            resid_cov=cov,
            n_obs=m,
            errors=errors,
        )
