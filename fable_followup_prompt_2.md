Strong session — the pro-rata falsification experiment, the 64-observation scoring table, and catching the v8 attribution confound yourself are exactly the standard we want. Three things before you touch quote width or run the shrinkage-alone retest.

## 1. Clarify what `w ≈ 0.5·σ` is actually solving for

You derived `0.5·σ` from the calibration test — it makes quoted width track your *own pricing error* well. But the original Component 1 theory (winner's curse) said width needs to *exceed* typical error by roughly `E[max_N Z]` (~0.56–1.03σ, N-dependent) specifically to survive adverse selection from RFQ competition — not just match your error on average.

Answer explicitly, in `REFERENCE.md`: is `0.5·σ` meant to be the *entire* quoted half-width, or is it meant to be combined with a separate winner's-curse buffer on top when this actually gets wired into quoting logic? If it's meant to be the whole thing, justify that with evidence — not just "mean σ is 2× mean error," which only shows σ is a conservative estimate of *pricing* error, and says nothing about whether it also covers the *selection* effect from competing against other MMs on the same RFQ. If you can't currently justify collapsing both into one number, say so and keep them as two explicit terms until we have evidence to merge them. We do not want to rediscover the v6/v7 failure mode with better-calibrated inputs.

## 2. Confirm train/test separation on the calibration test

Did the 12,000-scenario calibration check use parameter draws independent from whatever was used to build the sampling-based σ estimator, or could there be any overlap? If there's any chance the same warm-up data informed both, the reported coverage (95.2% within σ, tail rate 15.8%) is optimistic and needs to be redone on a clean held-out set before it goes into `REFERENCE.md` as `CONFIRMED`.

## 3. Check sensitivity to the number of Monte Carlo draws

You used 12 draws from the estimator's sampling distribution. That's thin enough that some of the heavy-tail behavior you saw in the calibration test could be noise in σ itself rather than a genuine delta-method failure. Rerun the same calibration test at 50 and 100 draws and report whether the tail rate and std(z) stabilize or keep shifting. If they stabilize near the 12-draw numbers, fine, keep 12 for runtime reasons and say so explicitly. If they don't, that changes the conclusion about the delta-method vs. sampling-method comparison.

## Sequencing

Resolve all three before wiring σ into any quoting logic. This does not block the shrinkage-alone retest you proposed — that's still the right next single-change test and can proceed in parallel. Just don't let `0.5·σ` go into `REFERENCE.md` as a settled width formula until item 1 is answered with the same evidentiary bar as everything else this session.
