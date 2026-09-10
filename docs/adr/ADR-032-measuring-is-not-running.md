# ADR-032 - Measuring is a different act from running

## Status

Accepted.

## Context

The first real run produced a comparison between two models that did not survive being
repeated. Four runs of the same model against the same paper verified 2, 4, 3 and 2
quotations out of 4, 5, 7 and 3 - a rate between 43% and 80%. That spread is wider than the
gap the single-run comparison had appeared to show, so the comparison measured nothing.

This is not only a mistake to record. It blocks the work that comes next. The extraction is
thin - three to seven claims from a seven-page paper - and the obvious response is to change
the prompt. But with that variance, a single run before and a single run after cannot tell
an improvement from noise, and the project would be making changes on the strength of
numbers that mean nothing.

Everything needed is already recorded. Each run writes `quotations_checked` to the audit
trail with its counts. What is missing is a way to produce several runs without confirming
each one, and a way to read the spread rather than a point.

Repetition runs into the principle that sensitive actions are previewed and confirmed
before they run, and confirmation defaults to no. Asking once and acting five times is
exactly the shape that principle exists to forbid.

## Decision

**A separate command, `lacc measure`, rather than a `--repeat` flag on `lacc run`.**

The distinction is real rather than cosmetic. `run` does work and returns an answer;
`measure` characterises a configuration and returns a distribution. Keeping them separate
means `run` keeps its meaning exactly - one preview, one confirmation, one action - and the
repetition never becomes a modifier that could be attached to something with effects.

**The confirmation is for the repetition, not for one action with a multiplier hidden
behind it.** The preview says how many times, and the person approves that. A prompt that
said "Proceed?" while meaning "five times" would be the deception this decision is trying to
avoid.

**`measure` refuses any skill that writes.** Measurement observes; it does not act. A skill
declaring `write_files` is rejected before anything runs, so repetition can never multiply
an effect. This is enforced by the capabilities the skill declares rather than by a list of
skill names.

**Every repetition is audited individually**, with its own run id, exactly as if it had been
run alone. A trail that recorded five executions as one would be a trail that lies about
what happened, and the count is the thing being measured.

**It reports the spread, not the average.** The point of the command is that a single number
misleads, so a mean would reproduce the error it exists to prevent. Minimum, maximum and
median per column, and a closing line naming the spread the person just measured.

## Consequences

- `lacc measure <skill> <path> --runs N` previews once, confirms once, runs N times, and
  prints the distribution of claims, verifications and rates.
- A skill that writes is refused with its reason; `revise_file` cannot be measured.
- The audit gains nothing new: `quotations_checked` already carries what is needed.
- Prompt and model changes become evaluable, which is what the next phase depends on.
- The default number of runs is deliberately more than one and small enough to be cheap.

## Trade-off

This creates a second way to execute a skill, and two paths to the same effects is how
control layers develop holes. Accepted because the second path is strictly narrower: it
refuses everything that writes, and it shares the same cycle, permissions and audit as the
first. It can do less than `run`, never more.

Repeating a run sends the document to the engine N times rather than once. That is
unavoidable if variance is to be measured at all, it is stated in the preview before anyone
agrees, and it goes to the same engine the configuration already names.

A person who wanted to run something five times can now do so without five confirmations,
and that is a small loosening of the human-in-the-loop promise. Accepted, narrowly: the
action is identical each time and was shown once in full, which is the condition under
which one approval honestly covers the repetition. It would not hold if the action varied
between runs, and `measure` does not let it vary.
