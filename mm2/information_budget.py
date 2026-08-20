"""Information budget per session: what CAN be learned in-session, and what cannot.

Two candidate adaptation signals, with very different information content:
  (A) realised PnL / settled markouts -- what every detector we built used
      (pooled-z, drawdown brake). Each settled binary contributes a Bernoulli
      outcome whose noise (sd ~ sqrt(p(1-p))) dwarfs our per-trade edge.
  (B) observed ORDER PRICES vs our theo -- FOK prices are observed directly,
      whether or not we trade, with NO payoff noise at all.

This computes the detectable effect size for each, given the real session length
established in E55 (~1 RFQ + 1 FOK per day over ~20-25 days).
"""
import math

Z_ALPHA, Z_POWER = 1.645, 0.84          # 95% one-sided, 80% power
NEED = Z_ALPHA + Z_POWER                # required |mean| / SE

print("=" * 72)
print("SESSION SIZE (from VERBOSE counts, E55): ~1 RFQ/day + ~1 FOK/day, ~20-25 days")
print("=" * 72)
n_days = 22
n_fok_seen = n_days * 1          # observed whether or not we trade
n_fills = 15                     # our actual fills per session (order of magnitude)
n_settles = n_fills

print(f"  FOK prices observed (no trade needed) : ~{n_fok_seen}")
print(f"  our fills / settled trades            : ~{n_fills}\n")

print("=" * 72)
print("(A) ADAPTING ON REALISED PnL  -- the channel every failed detector used")
print("=" * 72)
# a settled binary at price p: realised edge has sd ~ sqrt(p(1-p)); our per-trade
# edge is the quoted half-width (~4c) -- so the per-trade z is edge/sd.
for p in (0.5, 0.2, 0.05):
    sd = math.sqrt(p * (1 - p))
    edge = 0.04
    delta = edge / sd                              # per-trade effect size in sd
    n_needed = (NEED / delta) ** 2
    print(f"  option at theo {p:>4}: per-trade sd {sd:.3f}, edge {edge:.2f} "
          f"=> delta {delta:.3f} sd")
    print(f"      fills needed to detect our own edge: {n_needed:>7.0f}   "
          f"(we get ~{n_settles})  -> short by {n_needed / n_settles:>5.0f}x")
print("\n  => Detecting our OWN edge quality within a session is hopeless by ~2 orders")
print("     of magnitude. This is why pooled-z and the drawdown brake false-fired")
print("     9-24%: they were reading noise. Not a tuning problem -- an information")
print("     limit.\n")

print("=" * 72)
print("(B) ADAPTING ON OBSERVED ORDER PRICES -- no payoff noise")
print("=" * 72)
# each observed FOK gives (price - our theo) directly; dispersion across orders
# is the only noise. VERBOSE edges vs our theo: +6, +12, +2, +4, +5 cents.
obs = [0.06, 0.12, 0.02, 0.04, 0.05]
m = sum(obs) / len(obs)
sd_obs = (sum((x - m) ** 2 for x in obs) / (len(obs) - 1)) ** 0.5
print(f"  VERBOSE FOK edges vs our theo: {[f'{x:+.2f}' for x in obs]}")
print(f"  mean {m:+.3f}, dispersion sd {sd_obs:.3f}")
for n in (10, 20, 40):
    se = sd_obs / math.sqrt(n)
    detectable = NEED * se
    print(f"  after {n:>2} observed orders: SE {se:.4f}  -> can detect a mean-edge "
          f"shift of {detectable:+.3f} ({detectable * 100:.1f}c)")
print(f"\n  => With ~{n_fok_seen} observed orders we can resolve the flow's mean edge to")
print(f"     about +/-{NEED * sd_obs / math.sqrt(n_fok_seen) * 100:.1f}c -- comparable to our 3.5c base edge.")
print("     Distinguishing a donating flow (+10c) from a toxic one (-5c) IS feasible")
print("     on this channel, unlike on the PnL channel.\n")

print("=" * 72)
print("CONCLUSION")
print("=" * 72)
print("  Adaptation is not impossible -- but it must read the channel that carries")
print("  information. Order prices are observed directly and noise-free; realised")
print("  PnL is buried under Bernoulli variance ~10x the signal. Every detector we")
print("  built and rejected used the wrong channel.")
