# Akuna Capital 2026 Binary-Options Market Maker

An independently developed market-making strategy for Akuna Capital's simulated
2026 quantitative-trading challenge. The project combines an exact binary-option
pricer, warm-up parameter estimation, margin-aware quoting, counterparty tracking,
and a measured capacity-capture policy.

> **Verified result:** 18.3/20 on the visible grader suite (Run 15), with no
> bankruptcies. This is a competition simulator result, not live-market trading
> performance or a claim about profitability with real capital.

## Submission

The canonical, self-contained grader file is
[`submission/Market_Maker.py`](submission/Market_Maker.py). It is byte-identical
to the locked 18.3 build at
[`research/round1/Market_Maker_6.py`](research/round1/Market_Maker_6.py).

The bot implements the grader's `MarketMaker` interface directly. The submission
uses only Python's standard library; it has no runtime package installation step.
For the historical development validations, use Python 3.11 or newer.

## Strategy

### Pricing

The pricing core factors the market model into a dynamic program over the
quarter-point FED rate grid and conditional lognormal calculations for AJR and
THR. AJR-versus-THR spread options use a closed-form conditional distribution.
The official THEO test reported `max_error=0.0000` in the saved grader runs.

### Risk and quoting

Each trade reserves its maximum possible loss. RFQ sizes are budgeted from free
cash, with inventory skew, parameter-uncertainty-aware widths, per-counterparty
classification, and a selective FOK policy. The final 18.3 version adds two
empirically validated capture mechanisms on small-capital books:

- A low-priced RFQ ladder that disarms after the first lost auction, so it does
  not require identifying the opposing roster in advance.
- Increased quote-lock budgets on books up to $10.50, which improved the TC6
  ranking from 0.4 to 0.7 while preserving the higher-capital test results.

The exact score and detailed evidence are documented in the
[formal problem analysis](research/round1/PROBLEM.md),
[solution notes](research/round1/SOLUTION.md), and
[experiment log](research/round1/MEMORY.md).

## Results

| Run | Build | Total score | Change |
|---|---|---:|---:|
| 12 | Baseline | 17.4/20 | -- |
| 13 | Small-book capture ladder | 18.0/20 | +0.6 |
| 14 | Small-book budget increase | 18.0/20 | TC6 improved, no rank flip |
| 15 | Final mm6 | **18.3/20** | +0.3 |

In Run 15, TC5 scored 1.0 and TC6 improved from 0.4 to 0.7. Tests outside the
intended small-book range remained unchanged across the final submissions. The
captured PnL was $222.41 across the visible ranked tests; PnL is not the grader's
primary score, which is rank-based.

## Validation

The final build passed the local pricing/mechanics validation, fuzz checks,
stress tests, and an out-of-domain solvency suite. The working scripts and saved
grader logs are retained under [`research/round1/`](research/round1/).

From the repository root, run the main local checks with:

```powershell
python research/round1/validate_mm2.py
python research/round1/fuzz_edge_cases.py
python research/round1/stress_mm2.py
python research/round1/stress_out_of_domain.py
```

Compare two saved grader outputs with:

```powershell
python research/round1/run_diff.py `
  research/round1/Compiler_Messages_Run_14.txt `
  research/round1/Compiler_Messages_Run_15.txt
```

The historical analysis scripts are preserved as research artifacts. Some were
written for an earlier working-directory layout; the core validation commands
above are the supported entry points.

## Repository map

| Path | Contents |
|---|---|
| [`submission/`](submission/) | Canonical grader-ready 18.3 Python file |
| [`docs/REFERENCE.md`](docs/REFERENCE.md) | Mathematical and simulator reference |
| [`docs/source-material/`](docs/source-material/) | Challenge prompt, transcript, and reviewed 2025 entry |
| [`research/round1/`](research/round1/) | Final-round variants, logs, validation, analysis, and experiment history |
| [`research/legacy-v9/`](research/legacy-v9/) | Earlier strategy track and its experiments, retained for provenance |
| [`archive/prompts/`](archive/prompts/) | Original planning and review prompts |

## Limitations and interpretation

- The score is specific to the challenge's simulated markets and fixed visible
  test suite. It does not establish performance on real exchanges.
- The local arena is useful for stress and mechanism checks, but its absolute
  rankings did not reliably predict the grader. Live grader results take
  precedence in the experiment record.
- Per-counterparty learning is constrained by the small number of observations
  per counterparty. The classifier is retained, but should not be described as a
  high-frequency adaptive edge.
- The small-book gates are deliberate. A later experiment that removed the gate
  lost 0.4 points on the visible suite; do not remove it without a new, relevant
  evaluation.
- Historical variants are research artifacts, not alternate recommended
  submissions. Use `submission/Market_Maker.py` for the recorded final build.

## Context

This repository is a research and engineering portfolio piece. The experiment
log preserves both successful and failed hypotheses, the evidence used to
accept or reject them, and corrections made when a test harness was wrong.
Challenge materials and third-party research artifacts are kept in the clearly
labeled source-material folder; they are not presented as original work.