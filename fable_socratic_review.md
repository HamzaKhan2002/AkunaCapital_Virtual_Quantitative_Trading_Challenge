# SOCRATIC REVIEW — before you write another line of strategy code

You now have the full problem statement and the template code. You've already produced a strong theoretical decomposition (RFQ vs. FOK, winner's curse, Kelly sizing, tournament variance). Before we build on it, I want you to re-read the actual problem statement against your own analysis and answer the questions below yourself — don't wait for me to tell you the answers. If a question exposes a gap, fix it in `REFERENCE.md` and `MEMORY.md` before proceeding.

## 1. The scoring function

You derived "score ≈ 0.4 + 0.6·Φ(ΔE/√(Var_us+Var_opp))" from one observed session (Stalemate). Now go back to the literal text of the problem statement.

- What does the problem statement actually say determines your score? Quote it exactly.
- Is "full credit for being top MM by PnL, zero for bankruptcy, partial credit for avoiding bankruptcy" the same claim as your Φ() formula, or did you substitute a smooth continuous approximation for something that might be closer to a step function, a rank ordinal, or something else entirely?
- What would "partial credit for avoiding bankruptcy" even mean mechanically? Partial credit scaled by what — relative PnL rank, distance from the leader, absolute PnL, something else? Do you have any evidence for this, or are you still guessing?
- Given you don't yet know the exact functional form, does the tournament-theory prescription ("increase variance when behind") still hold under every plausible functional form consistent with the literal text, or only under your specific guessed one? Test this before committing resources to Component 5.

## 2. Bankruptcy mechanics — re-read the timing carefully

- When exactly is solvency checked? Continuously, or at a specific point?
- What happens to expired-option payoffs relative to that check — do they get applied before or after the solvency test, and can they move your balance in more than one direction?
- Given that timing, is "increase variance to improve rank" actually free, or does it interact with an intra-day accumulation of margin debits that could compound before any offsetting payoff arrives? Walk through a concrete multi-day scenario where you're behind on day 3 of 10 and decide to take on more risk — where exactly could this go wrong given the real settlement timing, not your prior assumption about continuous mark-to-market risk?

## 3. Who exactly are you bidding against on an RFQ?

You built a winner's-curse correction using a fixed table for N = 2, 3, 4 competing quotes.

- Where in the problem statement is N specified? Is it constant across the session, constant within a test, or explicitly stated to vary?
- Re-read the sentence about tests varying "via different counterparties and different competing market makers." What does that imply about whether you can know N in advance — at design time, at the start of a test, or only by observing fill behavior as you go?
- If N is not knowable in advance, what statistic could you compute online, from your own fill history within a session, that would let you infer something about effective competition without ever being told N directly? What would happen to your spread-width formula if you simply don't correct for N until you have that estimate — is an uncorrected width safer or more dangerous than an over-corrected one, and why?

## 4. FOK — did you actually model the mechanism, or a simplification of it?

You framed `respond_to_fok` as an individual Kelly-sizing decision: given price c and belief p, decide how much to take.

- Re-read exactly what happens when multiple market makers want the same FOK order. What is the actual allocation rule when demand exceeds what a single MM can take, per the statement?
- If your Kelly-optimal size is X, but you might only receive some fraction of X because others also want it, does that change what X you should compute in the first place, or only what you should expect to receive? Is there a difference between "the size I want" and "the size I should signal wanting," given the mechanism?
- Is there any information content in how much of an FOK order gets filled to you versus how much goes to competitors? Could that be a signal about how confident other market makers are, that you could exploit in later quoting or FOK decisions within the same session?

## 5. You built a univariate pricer. Is the actual instrument universe univariate?

- Re-read the third example event type. What does it require you to model that a single-underlying binomial-tree-plus-noise pricer, of the kind in the Luthra notebook, cannot capture on its own?
- What minimal joint-distribution structure would you need between AJR and THR to price a "which is higher" spread option correctly? Is correlation alone sufficient, or do you need the full joint distribution of terminal values?
- Does `MarketParameters`, as defined in the template, already expose a correlation or joint structure, or would you have to infer one from `MarketHistory`? Go check the actual template code and tell me which it is — don't assume.

## 6. Are FED, AJR, and THR the same kind of asset?

- A policy rate, and two private company valuations, are not obviously generated by the same stochastic process in reality. Does the template's `MarketParameters` treat all three symmetrically, or does it expose different parameterizations per underlying?
- If it does distinguish them, what does that tell you about whether a single generic pricing/estimation routine is even the right architecture, versus three underlying-specific models sharing a common interface?
- Would a naive single-model-fits-all approach silently mis-specify one of these three assets in a way that would only show up on certain test difficulties, per the note that "tests will also vary in difficulty"? How would you design a diagnostic to catch that before submission, rather than discovering it live?

## What I want back

Don't just answer these narratively. For each of the six sections:
1. State what you find when you actually check (template code, problem statement, or your own prior assumption).
2. State explicitly whether your prior analysis (the five-component plan) needs to change, and how.
3. Update `REFERENCE.md` and `MEMORY.md` accordingly — mark anything you previously wrote as fact but can't actually source as `HYPOTHESIS:` or `UNKNOWN` until you've checked.

Only after this review is done should we talk about writing the `MarketMaker` implementation itself.
