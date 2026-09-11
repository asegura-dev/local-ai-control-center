# ADR-034 - Showing what the document does say

## Status

Accepted.

## Context

At temperature zero the 14B model verified four of seven quotations from a real paper. The
other three were reported as *not in the document*, and that is where LACC stopped.

Looking at one of them changed how serious this is. The model wrote:

> The sensitivity of the AI method for detecting pelvic lymph node metastases was **76-90%**

The paper says:

> Results The sensitivity of the AI method for detecting pelvic lymph node metastases was
> **82%**

It did not invent a sentence. It took the results sentence and changed the figure. That is
the most dangerous shape a fabrication can take: the structure is right, the wording is
right, the topic is right, and only the number - the part that would go into a table - is
false. Nobody skimming catches it.

LACC catches it, and then throws away what it knows. Verifying a quotation means searching
the document; when the search fails, the tool has the document in hand and says nothing
more than "not found". The person is left to open a PDF and hunt for a sentence they now
know is wrong, without being told what is right.

## Decision

**When a quotation is not found, LACC reports the closest text that is actually in the
document.**

```
NOT IN THE DOCUMENT
  the model wrote:   ...metastases was 76-90%
  closest in source: Results The sensitivity of the AI method for detecting
                     pelvic lymph node metastases was 82%
```

**The verdict does not change.** It is still *not found*, and nothing fuzzy is ever
accepted as verified. ADR-026 decided that a quotation which only nearly appears is not a
quotation, and that stands: this adds a repair hint beside the refusal, it does not soften
the refusal.

**Nothing is shown below a similarity threshold.** A weak match is worse than silence,
because a suggestion carries an implication that someone will act on. The cutoff is the
same 0.6 that `difflib` uses by default, chosen because it is a published default rather
than a number tuned until the examples looked good.

**The wording describes, it does not assert intent.** "Closest text in the source", never
"the document says" or "you probably meant" - LACC has matched strings, and it does not
know what the model was reaching for.

**Candidates are sentences.** A quotation spanning a sentence boundary will match less well
than one inside a single sentence, which is a real limit and is written down rather than
engineered around. Every quotation in the runs that motivated this was a single sentence,
because that is what the skill asks for.

## Consequences

- `CheckedClaim` carries the nearest text, empty when nothing was close enough.
- A rejected claim becomes a lead rather than a dead end: the reader gets the true figure
  instead of only the news that the false one is false.
- The comparison is pure text against text, with no model asked to judge another model.
- This is something a tool holding both the document and the check can do and a chat
  service cannot, which is the same argument that justified the check itself.

## Trade-off

A suggestion can mislead. Shown next to a refusal, "closest text" may be read as "what the
model meant", and for a fabrication with no real counterpart the nearest sentence is
unrelated. Accepted, mitigated by the threshold and by wording that reports a match rather
than a reconstruction - and weighed against the alternative, which is a person hunting
through a PDF for a sentence they have been told does not exist.

It also makes an unverified claim more comfortable to work with, and comfort is not always
a virtue here: the point of marking a claim is that someone should open the document. A
reader who takes the suggestion and moves on has done less checking than one who was given
nothing. Accepted because the suggestion is drawn from the document itself, so acting on it
is acting on the source rather than on the model - but it is worth naming that this makes
the failure easier to live with, and that is not the same as making it rarer.
