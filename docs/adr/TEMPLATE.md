# ADR-NNN - A sentence, not a noun

<!--
Copy this file, number it, and delete these comments as you fill them in.

The title says what was decided, not what the feature is called. "Metadata from a registry,
not from a model" beats "Crossref integration": the first carries the argument, the second
carries a vendor.
-->

## Status

<!--
Accepted, superseded by ADR-NNN, or reversed. Add the one sentence that places it: what
found this, or what it is answering. "Found by assembling a real corpus and looking at the
file, not by any check here" tells a reader in one line how much to trust it.
-->

## Context

<!--
What is true right now that makes this worth deciding. Numbers if there are any, and there
usually are - `tools/measure.py` takes most of them in one run.

If a figure appears here, say when it was taken. This project repeated a true sentence for
days after it stopped being true, and that is the failure it has recorded most often.
-->

## Decision

<!--
What was decided, in bold sentences that can be disagreed with. One per paragraph.

The useful shape is "X, because Y" where Y is measured or is a principle already written
down. A decision whose reason is "it seemed cleaner" is a preference, and preferences belong
in a commit message rather than here.

Say what was REFUSED as well as what was chosen. Half the value of these records is the road
not taken: no contact address sent to Crossref, no abstract read, no second copy of the
command list. A future reader needs to know those were considered.
-->

## What was measured

<!--
Optional, and the section that makes the difference when it is there.

A table of what was counted before deciding. If the measurement changed the plan, say so -
"counting refused half the idea" is the most useful sentence a record can contain, and it
happened twice here.

If nothing was measured, leave this out rather than inventing a figure. An absent section is
honest; a decorative one is not.
-->

## Consequences

<!--
What is now true that was not. Commands that exist, tests that were added, files that other
things now depend on.

Include the boring ones: an override added to mypy, a layer the layout test had to learn.
Those are what somebody hits later.
-->

## Trade-off

<!--
Never empty. If this section is hard to write, the decision has not been understood yet.

What this costs, what it does not protect against, and what a reasonable person would object
to. Write the strongest version of the objection rather than a weak one you can answer.

"A named-exception list is a thing that can be added to. Nothing mechanical stops someone
appending a name instead of moving a function, and the honest answer is that this record is
where that would be visible, not the test."
-->
