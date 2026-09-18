# ADR-058 - Controls that did not cover what they claimed

## Status

Accepted. Two findings from a deliberate sweep for this shape, after ADR-055 and ADR-056
showed it twice in two days.

## Context

ADR-055 found a feature nothing could switch on. ADR-056 found a parser discarding an answer
it had been given. Both passed their tests. Both were described accurately in a document and
inaccurately in the program. So the codebase was swept for the same shape: **things that are
defined, documented and tested, and do not reach what they claim to reach.**

Two were found.

### Deduplication covered one of the four paths that produce checked claims

`without_repeats` drops a quotation already seen, or wholly inside one already seen
(ADR-054). Four places in LACC turn an answer into checked claims:

| | |
|---|---|
| `cycle.py` - reading in passes | **deduplicated** |
| `cycle.py` - the ordinary run | not |
| `cli.py` - `measure` | not |
| `cli.py` - `ask` | not |

Only the passes path, because that is the path ADR-045 was thinking about when it wrote
*"a document read in overlapping passes offers the overlapping page twice"*. The reasoning was
about how the repeat arose rather than about what it costs.

**A single answer repeats passages too, and it was measured doing so.** One paper, one call,
no passes: nineteen quotations of which **three** are repeats or contained in another. Across
the 654-quotation corpus, six. Every one of those reached the corpus, because `collect` runs
the ordinary path.

### ntfy promised basic credentials it could not use

`NtfyNotifier`'s docstring said *"Authenticates with a bearer token when one is configured, or
basic credentials."* `basic_authorization()` existed and had a test asserting it encodes
correctly, titled *"For a server behind basic auth rather than a token."*

**Nothing called it**, and there was no configuration field for a username or a password, so
no user could have reached it. A person whose ntfy server wants basic auth would have read
that docstring, believed it, and found nothing.

## Decision

**Deduplication applies wherever an answer becomes checked claims.** All four paths. Which
code path read the document is not a reason for one corpus to hold a sentence twice and
another not to, and the trade ADR-054 argued - a second reading of one passage is lost, and a
corpus with the same sentence twice is worse - does not depend on the route either.

**The basic-credentials helper is removed, and the docstring now says what is true.** Removed
rather than wired: there was no user need, no configuration surface, and adding an untested
authentication path to make a sentence true is worse than correcting the sentence. If someone
needs it, it arrives with a configuration field and a test through the real path.

## Consequences

- Counts drop slightly and everywhere: the measured paper reports sixteen quotations where it
  reported nineteen. The tool now reports what a reader receives.
- `measure` and `run` agree. They did not, which made `measure` characterise a configuration
  nobody runs.
- ntfy authenticates with a bearer token, and says only that.

## Trade-off

**Every published count from before this is on the undeduplicated basis.** The corpus figures
in chapter 4 - 654 quotations, 548 in their document - counted repeats as separate. The
correction is small and known: six of 654. It is named rather than quietly re-run.

**Removing a capability is a loss for whoever wanted it**, even one nobody could use. The
record says exactly what was removed and what it would take to have it.

## What the sweep is worth

Two findings in one pass, after two in two days, is not a reason for confidence that the
fourth was the last. What can be said is narrower: **the reachability test added in ADR-055
would not have caught either of these.** It asks whether a setting can be set. Neither of these
is a setting - one is a control applied in three fewer places than it should be, the other a
sentence in a docstring. There is no test for *does this cover what its record says it
covers*, and the honest answer is that reading is what found them.
