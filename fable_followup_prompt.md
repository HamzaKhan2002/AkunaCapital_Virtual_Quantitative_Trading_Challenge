Good work on this pass — the FOK correction and the bankruptcy-timing derivation are exactly the standard we want: you found receipts, you found where you were wrong, and you marked one thing `UNKNOWN` instead of guessing. Three things in this round don't yet meet that same bar. Go find receipts for them the same way you did for `FokOrder`, or mark them `UNKNOWN` if the receipts aren't there.

## 1. The RFQ split rule — you inferred it, you didn't verify it

You concluded "N is inferable online" from TC2: bid 0.00 on "sell 6", received exactly 3, therefore "equal split ⇒ exactly one other MM at our price." That's one arithmetic coincidence, not a verified allocation rule. It's equally consistent with size-weighted allocation, time-priority with rounding, or multiple MMs at different price levels with partial allocation to the best price.

Do the same thing you did for `FokOrder`: grep the matching engine / exchange-side code (not just the classes we're told to fill in) for how RFQ fills get split among tied or competing quotes. If you find the actual rule, cite it and redo the N-estimator on that basis. If you don't find it — and it may genuinely not be exposed, since we can only read what we're given — mark the split mechanism `UNKNOWN` in `REFERENCE.md` and `MEMORY.md`, and say explicitly what alternative allocation rules would break your online N-estimator, so we know how fragile it is.

## 2. The scoring law — show the table, not just the fit

You're calling `0.4 + 0.6·(beaten/n)` an `EMPIRICAL LAW` fitted to "16 test cases × 5 runs, exact to two decimals every time." Show me the actual raw table: for each observation, the values of `beaten`, `n`, and observed score. I want to see:
- How many distinct values of `n` actually appear in that data — if it's only 2 or 3 distinct values, "exact fit" is much weaker evidence than it sounds.
- What happens at the boundaries: `beaten = 0` (does it always hit exactly 0.40?) and `beaten = n` (does it always hit exactly 1.00, or is there headroom above 1.00 for exceptional performance?).
- Whether any observation contradicts the linear form, even slightly.

If the raw data actually supports it cleanly, fine — upgrade it to `CONFIRMED` in `MEMORY.md` with the table attached as evidence. If the sample is thin or boundary behavior is unverified, keep it as `HYPOTHESIS` and say what additional test result would confirm or break it.

## 3. Per-test score vs. final score — you haven't addressed this at all

The original problem statement says the 16 SCORED tests "will also vary in difficulty." You've been treating your rank formula as if it applies uniformly and as if per-test scores simply average (or sum) into a final grade. Go check: is there any indication of how the 16 individual test scores combine into whatever number actually determines outcome (e.g., equal-weighted average, difficulty-weighted, best-N-of-16, threshold-based)? If the template, problem statement, or any test harness output gives evidence either way, cite it. If there's genuinely no information, mark this `UNKNOWN` explicitly and tell me whether your current strategy is robust to the aggregation rule being any of the plausible options, or whether it implicitly assumes one specific rule.

## Standard for this pass

Same rule as last time: distinguish `CONFIRMED` (you found it in code/spec, cite the exact location or line), `HYPOTHESIS` (plausible, evidence points that way, but not proven), and `UNKNOWN` (you looked and it's genuinely not exposed). Don't let anything stay in the document with more confidence than the evidence actually supports. Update `REFERENCE.md` and `MEMORY.md` accordingly, and tell me explicitly which of these three items changed status and which of our current strategy decisions (if any) depend on the ones still marked `HYPOTHESIS` or `UNKNOWN`.

Once these three are resolved or properly downgraded, proceed with Component 2 (parameter-uncertainty estimation) as agreed — that's still the keystone and nothing here should block it.
