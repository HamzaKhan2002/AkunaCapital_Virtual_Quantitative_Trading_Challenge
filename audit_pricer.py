"""Numerical audit of every formula in REFERENCE.md against brute-force Monte Carlo.

Process audited: S_{t+1} = S_t + (+u w.p. p | -d w.p. q) + N(0, sigma^2), no floor/rounding.
Binary call pays 1[S_T > K].
"""
import math
import numpy as np

SQRT2 = math.sqrt(2.0)
SQRT2PI = math.sqrt(2.0 * math.pi)


def ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / SQRT2))


def npdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / SQRT2PI


# --- REFERENCE §2.3: exact mixture pricer ---
def price_call(S, K, T, u, d, p, sigma):
    q = 1.0 - p
    if T == 0:
        return 1.0 if S > K else 0.0
    tot = 0.0
    for nu in range(T + 1):
        w = math.comb(T, nu) * p**nu * q ** (T - nu)
        ST = S + nu * u - (T - nu) * d
        if sigma > 0:
            tot += w * ncdf((ST - K) / (math.sqrt(T) * sigma))
        else:
            tot += w * (1.0 if ST > K else 0.0)
    return tot


def price_put(S, K, T, u, d, p, sigma):
    q = 1.0 - p
    tot = 0.0
    for nu in range(T + 1):
        w = math.comb(T, nu) * p**nu * q ** (T - nu)
        ST = S + nu * u - (T - nu) * d
        tot += w * (1.0 - ncdf((ST - K) / (math.sqrt(T) * sigma)))
    return tot


# --- REFERENCE §4.1: analytic Greeks ---
def delta_analytic(S, K, T, u, d, p, sigma):
    q = 1.0 - p
    tot = 0.0
    for nu in range(T + 1):
        w = math.comb(T, nu) * p**nu * q ** (T - nu)
        z = (S + nu * u - (T - nu) * d - K) / (math.sqrt(T) * sigma)
        tot += w * npdf(z)
    return tot / (math.sqrt(T) * sigma)


def gamma_analytic(S, K, T, u, d, p, sigma):
    q = 1.0 - p
    tot = 0.0
    for nu in range(T + 1):
        w = math.comb(T, nu) * p**nu * q ** (T - nu)
        z = (S + nu * u - (T - nu) * d - K) / (math.sqrt(T) * sigma)
        tot += w * z * npdf(z)
    return -tot / (T * sigma**2)


def check(name, got, want, tol):
    ok = abs(got - want) <= tol
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got={got:.8f} want={want:.8f} |diff|={abs(got-want):.2e} tol={tol:.1e}")
    return ok


def main():
    rng = np.random.default_rng(7)
    # Deliberately asymmetric (u != d), drift-free: p = d/(u+d)
    u, d = 1.0, 2.0
    p = d / (u + d)
    q = 1.0 - p
    assert abs(p * u - q * d) < 1e-12
    sigma, S0, T, K = 0.8, 100.0, 8, 101.0
    c = p * u

    results = []

    # 1. Pricer vs brute-force MC of the actual process
    N = 4_000_000
    moves = np.where(rng.random((N, T)) < p, u, -d).sum(axis=1)
    noise = rng.normal(0.0, sigma, (N, T)).sum(axis=1)
    ST = S0 + moves + noise
    V = price_call(S0, K, T, u, d, p, sigma)
    V_mc = float((ST > K).mean())
    mc_se = math.sqrt(V_mc * (1 - V_mc) / N)
    results.append(check("§2.3 pricer vs MC (4M paths)", V, V_mc, 4 * mc_se))

    # 2. Terminal variance T(c(u+d)+sigma^2)
    results.append(check("§2.7 Var[S_T] = T(c(u+d)+σ²)", T * (c * (u + d) + sigma**2), float(ST.var()), 0.05))

    # 3. Martingale E[S_T] = S_0
    results.append(check("§2.7 E[S_T] = S_t (martingale)", float(ST.mean()), S0, 4 * float(ST.std()) / math.sqrt(N)))

    # 4. Parity V_c + V_p = 1 (sigma > 0)
    results.append(check("§2.5 parity V_c + V_p", price_call(S0, K, T, u, d, p, sigma) + price_put(S0, K, T, u, d, p, sigma), 1.0, 1e-12))

    # 5. Tower property E_t[V_{t+1}] = V_t  (branch enumeration + fine noise quadrature)
    xs = np.linspace(-8 * sigma, 8 * sigma, 40001)
    pdf = np.exp(-0.5 * (xs / sigma) ** 2) / (sigma * SQRT2PI)
    ev = 0.0
    for move, prob in ((u, p), (-d, q)):
        vals = np.array([price_call(S0 + move + e, K, T - 1, u, d, p, sigma) for e in xs])
        ev += prob * float(np.trapz(vals * pdf, xs))
    results.append(check("§8.6 tower E[V_{t+1}] = V_t", ev, V, 1e-6))

    # 6. Closed-form identity E[Φ(α+βε)] = Φ(α/√(1+β²)), ε~N(0,1)
    alpha, beta = 0.3, 0.7
    xs1 = np.linspace(-10, 10, 40001)
    lhs = float(np.trapz(np.array([ncdf(alpha + beta * x) * npdf(x) for x in xs1]), xs1))
    results.append(check("§8.6 E[Φ(α+βε)] identity", lhs, ncdf(alpha / math.sqrt(1 + beta**2)), 1e-8))

    # 7. Analytic delta vs central finite difference
    h = 1e-5
    d_fd = (price_call(S0 + h, K, T, u, d, p, sigma) - price_call(S0 - h, K, T, u, d, p, sigma)) / (2 * h)
    results.append(check("§4.1 Δ analytic vs FD", delta_analytic(S0, K, T, u, d, p, sigma), d_fd, 1e-7))

    # 8. Analytic gamma vs finite difference
    h = 1e-4
    g_fd = (price_call(S0 + h, K, T, u, d, p, sigma) - 2 * V + price_call(S0 - h, K, T, u, d, p, sigma)) / h**2
    results.append(check("§4.1 Γ analytic vs FD", gamma_analytic(S0, K, T, u, d, p, sigma), g_fd, 1e-4))

    # 9. Vega identity ν = TσΓ vs finite difference in σ
    hs = 1e-6
    v_fd = (price_call(S0, K, T, u, d, p, sigma + hs) - price_call(S0, K, T, u, d, p, sigma - hs)) / (2 * hs)
    results.append(check("§4.1 ν = TσΓ", T * sigma * gamma_analytic(S0, K, T, u, d, p, sigma), v_fd, 1e-5))

    # 10. Same-underlying covariance: calls K1<=K2, Cov = V(K2)(1-V(K1))
    K1, K2 = 99.0, 103.0
    V1, V2 = price_call(S0, K1, T, u, d, p, sigma), price_call(S0, K2, T, u, d, p, sigma)
    cov_mc = float(np.cov((ST > K1).astype(float), (ST > K2).astype(float))[0, 1])
    results.append(check("§5.4 Cov = V(K2)(1-V(K1)) vs MC", V2 * (1 - V1), cov_mc, 4e-4))

    # 11. Delta unboundedness: T=1, sigma=0.1, ATM -> Δ ≈ φ(0)/σ ≈ 3.99 > 1
    d_small = delta_analytic(100.0, 100.0, 1, 0.05, 0.05, 0.5, 0.1)
    print(f"INFO  §4.2 near-expiry ATM delta = {d_small:.3f} (>1 confirms unboundedness)")
    results.append(d_small > 1.0)

    # 12. CLT approximation quality (sanity check only)
    V_clt = ncdf((S0 - K) / math.sqrt(T * (c * (u + d) + sigma**2)))
    print(f"INFO  §2.7 CLT approx = {V_clt:.6f} vs exact {V:.6f} (diff {abs(V_clt-V):.4f} — sanity-level only, as documented)")

    # 13. Monotonicity in K and T→0 limit
    mono = all(
        price_call(S0, k, T, u, d, p, sigma) >= price_call(S0, k + 0.5, T, u, d, p, sigma)
        for k in np.arange(90.0, 110.0, 0.5)
    )
    print(f"{'PASS' if mono else 'FAIL'}  §8.6 V non-increasing in K")
    results.append(mono)
    # 13. σ→0 limit: strike OFF the lattice (no tie) collapses to lattice probability
    K_off = 100.5  # up node 101 > K_off, down node 98 < K_off
    lim = price_call(S0, K_off, 1, u, d, p, 1e-9)
    exp_lim = p * (1.0 if S0 + u > K_off else 0.0) + q * (1.0 if S0 - d > K_off else 0.0)
    results.append(check("§8.6 σ→0 collapses to lattice prob (no tie)", lim, exp_lim, 1e-9))

    # 14. §2.6 tie demonstration: strike ON a lattice node -> σ→0 limit gives HALF the node mass
    lim_tie = price_call(S0, 101.0, 1, u, d, p, 1e-9)  # up node lands exactly on K
    results.append(check("§2.6 tie: σ→0 limit = p/2 (neither > nor ≥ convention)", lim_tie, p / 2, 1e-9))
    print("INFO  §2.6 confirmed: at exact ties the noisy pricer limit is half-mass — the > vs ≥ convention MUST be read from live starter code")

    print(f"\n{'ALL CHECKS PASSED' if all(results) else '*** FAILURES PRESENT ***'} ({sum(bool(r) for r in results)}/{len(results)})")


if __name__ == "__main__":
    main()
