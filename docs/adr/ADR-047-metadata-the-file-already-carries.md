# ADR-047 - Metadata the file already carries

## Status

Accepted.

## Context

Asked for a paper's journal, a 14B model supplied one from memory twelve times out of
twenty-four, **with an explicit instruction in the same prompt not to use its own knowledge
and to write "not available" for anything missing**. Two of the twelve were wrong in a way
that would put a false citation in a thesis: a paper in *EJNMMI* attributed to *European
Radiology*, and one in *EJNMMI Physics* attributed to *EJNMMI*.

The obvious answer is an authority: send the DOI to Crossref and take back the record. That
answer has a cost this project's users have already refused. **A DOI sent to a third party
says what you are reading**, and a bibliography of DOIs says what you are working on. The
people this is built for chose a local tool for that reason.

Before designing around the cost, the alternative was measured. Publishers embed metadata in
the files they ship, and twenty-three PDFs from a real bibliography carry:

| | present |
|---|---|
| Title | 18 of 23 |
| Author | 15 of 23 |
| **DOI** | **11 of 23** |
| Journal | **1 of 23** |

The last row is the surprise and it decides the shape of this. What the embedded fields call
a publication is almost always the **publisher** - `Springer US`, `Elsevier Ltd`,
`Springer International Publishing` - and a publisher is not a journal. Only one file names
the journal it appeared in.

So the local source answers three of the four fields well and the fourth not at all.

## Decision

**LACC reports the metadata a file carries and nothing else.** Title, authors, DOI and date,
read from the document's own XMP and info dictionary. No network, no model.

**What is absent is reported as absent.** A field that is not in the file is "not available",
never inferred from the filename, never asked of a model. That sentence is the whole point:
the failure being fixed is a plausible answer where there should have been none.

**The journal is not reported at all, and the DOI is why.** With a correct DOI a reference
manager resolves journal, volume, pages and the rest, and does it against a record rather
than against a recollection. LACC does not need to know where a paper appeared; it needs to
hand over an identifier that can be trusted, and it has one for eleven of twenty-three
documents where the model had one for none.

**Crossref is deferred rather than rejected, and the reason is written here** so that adding
it later is a decision rather than a drift. If it arrives it is opt-in, gated behind
`network_access` like every other destination, and it says what it discloses before it
discloses it. A lookup that quietly tells a third party which oncology papers somebody is
reading is not a feature that belongs on by default in a tool chosen for being local.

## Consequences

- `embedded_metadata` joins the documents adapter, beside the outline reader; both answer
  "what does this file say about itself".
- `lacc metadata` prints it for one or many documents, and says which fields are missing.
- The five documents carrying nothing - two arXiv preprints, a statistics sheet and two
  guidelines - report nothing, which is correct and unhelpful, and is still better than a
  journal somebody made up.

## Trade-off

**Three fields out of four is worse than an authority would do**, and the gap is the one the
model was worst at. Somebody assembling a bibliography still has to supply journals by hand
or from their reference manager. Accepted: a blank field costs a minute and a wrong one
costs a correction after publication.

Embedded metadata can itself be wrong. A publisher's tooling writes it, and the title in a
file is occasionally the title of a template. This is not verified against anything, and
calling it "what the file says about itself" rather than "the metadata" is the most this can
honestly claim.

**Deferring Crossref means the decision gets made again later, under pressure, when somebody
wants a journal field filled.** Writing the privacy cost down now is what that future
decision will have to argue against, and it is deliberately the strongest version of the
argument: the cost is not hypothetical, it is the reason this project exists.
