"""Audit of the scoring law and aggregation rule against every logged grader run.

Observations transcribed from Compiler_Messages_Run_{1,2,3,5}.txt.
Each SCORED entry: (test, our_pnl, [opponent_pnls], observed_score).
"""
from itertools import groupby

# test: (our_pnl, [competitor pnls], observed score)
RUNS: dict[str, dict[int, tuple[float, list[float], float]]] = {
    "Run1": {
        5: (1.47, [43.0], 0.40), 6: (-0.43, [13.21, 1.0], 0.40), 7: (0.24, [21.62], 0.40),
        8: (1.47, [33.31, 2.0], 0.40), 9: (3.46, [32.12, 3.0], 0.70), 10: (5.83, [42.71, 5.0], 0.70),
        11: (-0.68, [6.01, 1.98], 0.40), 12: (-1.11, [-1.59], 1.00),
        13: (2.27, [20.47, 6.5, 3.35], 0.40), 14: (-0.92, [27.28, 12.39], 0.40),
        15: (2.92, [16.85, 7.13], 0.40), 16: (3.2, [17.57, 5.95], 0.40),
        17: (17.77, [17.97, 14.64, -16.93], 0.80), 18: (-2.5, [54.08, -0.07, -27.81], 0.60),
        19: (-5.03, [23.24, -11.72, -22.55], 0.80), 20: (-2.28, [-9.41, -33.5, -92.19], 1.00),
    },
    "Run2": {
        5: (1.91, [43.0], 0.40), 6: (-0.8, [13.04, 1.0], 0.40), 7: (0.97, [22.32], 0.40),
        8: (1.84, [34.36, 1.0], 0.70), 9: (16.83, [23.96, 2.76], 0.70), 10: (6.62, [42.03, 5.0], 0.70),
        11: (-0.94, [6.33, 1.98], 0.40), 12: (-1.71, [-0.56], 0.40),
        13: (4.28, [17.79, 6.9, 3.31], 0.60), 14: (-2.98, [28.06, 12.04], 0.40),
        15: (15.66, [16.2, 7.0], 0.70), 16: (11.39, [7.09, 6.78], 1.00),
        17: (13.96, [15.27, 15.19, -11.09], 0.60), 18: (9.45, [50.14, 0.34, -28.84], 0.80),
        19: (-7.66, [23.33, -7.6, -23.52], 0.60), 20: (-8.02, [-12.65, -33.45, -79.83], 1.00),
    },
    "Run3": {
        5: (1.91, [43.0], 0.40), 6: (0.26, [12.29, 1.0], 0.40), 7: (0.97, [22.32], 0.40),
        8: (1.84, [34.36, 1.0], 0.70), 9: (13.96, [27.86, 2.76], 0.70), 10: (6.1, [43.84, 4.0], 0.70),
        11: (-1.22, [6.65, 1.98], 0.40), 12: (-1.75, [-0.44], 0.40),
        13: (4.28, [17.79, 6.9, 3.31], 0.60), 14: (-3.28, [28.29, 12.54], 0.40),
        15: (15.63, [16.24, 6.95], 0.70), 16: (11.33, [7.24, 6.78], 1.00),
        17: (13.53, [15.03, 14.33, -9.74], 0.60), 18: (3.92, [55.85, 0.49, -28.82], 0.80),
        19: (-7.25, [23.76, -8.65, -23.19], 0.80), 20: (-8.02, [-12.65, -33.45, -79.83], 1.00),
    },
    "Run5": {
        5: (6.33, [37.0], 0.40), 6: (-1.55, [15.49, 1.0], 0.40), 7: (1.63, [22.32], 0.40),
        8: (1.35, [35.44, 1.0], 0.70), 9: (16.7, [25.46, 0.19], 0.70), 10: (11.95, [44.07, 0.0], 0.70),
        11: (-2.13, [7.14, 2.18], 0.40), 12: (4.59, [-4.76], 1.00),
        13: (9.17, [18.2, 6.93, 3.38], 0.80), 14: (-2.05, [27.81, 12.82], 0.40),
        15: (79.08, [11.72, 8.01], 1.00), 16: (12.48, [13.43, 1.89], 0.70),
        17: (25.0, [24.16, 16.13, -10.69], 1.00), 18: (3.92, [56.54, -0.63, -26.88], 0.80),
        19: (-3.61, [23.47, -13.71, -23.61], 0.80), 20: (-5.71, [-9.16, -33.67, -84.32], 1.00),
    },
}

REPORTED_TOTALS = {"Run1": 13.2, "Run2": 13.8, "Run3": 14.0, "Run5": 15.2}
NON_SCORED = 1.0 + 3.0  # THEO (max_error 0.0000) + 3 VERBOSE, all full marks in every run


def main() -> None:
    rows = []
    violations = []
    for run, tests in RUNS.items():
        for tc, (ours, opps, score) in sorted(tests.items()):
            n = len(opps)
            beaten = sum(1 for o in opps if ours > o)
            predicted = 0.4 + 0.6 * beaten / n
            ok = abs(predicted - score) < 1e-9
            rows.append((run, tc, beaten, n, f"{beaten}/{n}", score, predicted, ok))
            if not ok:
                violations.append((run, tc, beaten, n, score, predicted))

    print("=== RAW OBSERVATION TABLE (score law) ===")
    print(f"{'run':<6}{'tc':>3}{'beaten':>8}{'n':>3}{'frac':>7}{'observed':>10}{'predicted':>11}  ok")
    for r in rows:
        print(f"{r[0]:<6}{r[1]:>3}{r[2]:>8}{r[3]:>3}{r[4]:>7}{r[5]:>10.2f}{r[6]:>11.2f}  {'Y' if r[7] else 'N'}")

    print(f"\nobservations: {len(rows)}   violations: {len(violations)}")

    ns = sorted({r[3] for r in rows})
    fracs = sorted({r[2] / r[3] for r in rows})
    print(f"distinct n values observed : {ns}")
    print(f"distinct beaten/n observed : {[round(f, 4) for f in fracs]}")
    print(f"distinct scores observed   : {sorted({r[5] for r in rows})}")

    print("\n=== BOUNDARY BEHAVIOUR ===")
    for label, sel in (("beaten = 0", lambda r: r[2] == 0), ("beaten = n", lambda r: r[2] == r[3])):
        vals = sorted({r[5] for r in rows if sel(r)})
        cnt = sum(1 for r in rows if sel(r))
        ns_here = sorted({r[3] for r in rows if sel(r)})
        print(f"{label:<12} n={cnt:>3} obs, n-values {ns_here}, scores observed: {vals}")
    # headroom check: biggest blowout win still capped?
    wins = [(r[0], r[1], r[5]) for r in rows if r[2] == r[3]]
    blowout = max(
        ((run, tc, RUNS[run][tc][0], max(RUNS[run][tc][1]), RUNS[run][tc][2]) for run, tc, _ in wins),
        key=lambda t: t[2] - t[3],
    )
    print(f"largest margin of victory: {blowout[0]} TC{blowout[1]} ours={blowout[2]} vs best opp={blowout[3]} "
          f"-> score {blowout[4]} (no headroom above 1.00)")

    print("\n=== AGGREGATION RULE: does simple unweighted sum reproduce the reported total? ===")
    for run, tests in RUNS.items():
        scored_sum = sum(s for _, _, s in tests.values())
        total = NON_SCORED + scored_sum
        rep = REPORTED_TOTALS[run]
        print(f"{run}: SCORED sum {scored_sum:5.2f} + THEO/VERBOSE {NON_SCORED:.1f} = {total:5.2f} "
              f"| reported {rep:5.2f} | {'MATCH' if abs(total - rep) < 1e-9 else 'MISMATCH'}")

    print("\n=== RFQ SPLIT: size-invariance natural experiment (TC2/TC3 VERBOSE logs) ===")
    # (run, option, our quoted size at the winning price, order qty, fill we received)
    obs = [
        ("Run1", "8734500 sell-6 RFQ", 20, 6, 3),
        ("Run2", "8734500 sell-6 RFQ", 120, 6, 3),
        ("Run5", "8734500 sell-6 RFQ", 120, 6, 3),
        ("Run1", "1280022 buy-4 RFQ", 20, 4, 2),
        ("Run5", "1280022 buy-4 RFQ", 120, 4, 2),
    ]
    print(f"{'run':<6}{'event':<24}{'our size':>9}{'order':>7}{'fill':>6}{'equal-split':>13}{'pro-rata*':>11}")
    for run, ev, size, qty, fill in obs:
        equal = qty / 2
        prorata = qty * size / (size + 400)  # vs Stalemate's observed 400-lot quote
        print(f"{run:<6}{ev:<24}{size:>9}{qty:>7}{fill:>6}{equal:>13.1f}{prorata:>11.2f}")
    print("*pro-rata computed against Stalemate's observed 400-lot size")
    print("Our quoted size varied 20 -> 120 (6x) with IDENTICAL fills; pro-rata predicts 0.29 -> 1.4.")


if __name__ == "__main__":
    main()
