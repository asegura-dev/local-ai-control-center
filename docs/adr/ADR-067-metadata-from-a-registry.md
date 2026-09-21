# ADR-067 - Metadata from a registry, not from a model

## Status

Accepted. This is the first time LACC reaches a destination that is not the user's own
machine or their own network, so the record spends more of its length on what leaves than on
what arrives.

## Context

Asked for the journal a paper appeared in, with *"say not available for anything missing"* in
the prompt, a 14B **invented twelve journal names out of twenty-four** (ADR-047). The
instruction was explicit and it was negotiated away, which is this project's central measured
finding: what is structure is obeyed, what is a request is negotiated.

Reference metadata is the exact shape of thing a model produces plausibly and wrongly, and it
is the last thing standing between a corpus that is complete and a bibliography that can be
**handed in**. A thesis is not submitted with twelve invented journals in it.

`lacc references` already parses what each paper cites, from the document itself, with no
model and no network (ADR-064). What it recovers is the entry as printed plus a DOI when one
survives - **205 distinct DOIs** across the bibliography. A DOI is an identifier, not a
description: it says *which* work, and nothing about what the work is.

The only honest way to turn one into the other is to ask whoever assigns them.

## What leaves this machine, stated before anything else

**A DOI, and nothing else.** No document, no quotation, no corpus, no question, no filename,
and no text the user wrote. The request is a URL with a public identifier in it.

**And the honest part: the set of DOIs is the bibliography.** Resolving two hundred of them
tells the registry, in one session, what this project is reading. A single DOI reveals a
public identifier; the *list* reveals a line of research before it is published. That is a
real disclosure, it is not undone by any framing, and the decisions below exist to keep it
deliberate rather than incidental.

**No contact address is sent.** Crossref offers a faster queue to clients that identify
themselves with an email. That email is the user's, it is personal data, and trading it for
throughput is not a decision this project makes on someone's behalf. The public queue is
slower and is the default. A user who wants the faster one writes their own address in their
own configuration file, and then it is theirs to give.

**Nothing is downloaded.** Metadata is JSON. A PDF is a document, a document is a thing this
project treats as potentially hostile, and fetching one automatically would add an ingestion
path nobody asked for. The registry answers questions about works; it does not deliver them.

## Decision

**A port, because this is a different question asked of a different endpoint.**
`ports/registry.py` holds `Registry` - `about(doi) -> Work | None` - and the frozen `Work`
that crosses it. `None` is the answer for a DOI the registry does not know, which is
distinct from a failure to reach it at all.

**The destination is written in the configuration, by the user.** `registry_url` is empty by
default, and empty means off. This follows ADR-030 and ADR-060 exactly: a destination belongs
in the file the user wrote, never in an environment variable, and this project has already
had to remove one that arrived by that route.

**Two switches, and both must be on.** `network_access` is the ceiling and is off by default;
`registry_url` is the destination and is empty by default. Neither implies the other. A
configuration with the network enabled for the engine does not thereby resolve DOIs.

**The capability is `network`, not a new one.** The closed set of capabilities describes what
a skill may *do*; the destination describes where it may go, and this project already models
destinations as addresses in the configuration - `engine_host` for the engine, `server_url`
for the notifier. Inventing `resolve_dois` would put the same fact in two places and let them
disagree.

**Six fields, and the abstract is not one of them.** Title, authors, container title, year,
type, DOI. An abstract is the only long free-text field a registry returns; it is the obvious
carrier for an injection, and a bibliography does not need it. Refusing it removes the vector
rather than sanitising it.

**What comes back is treated as hostile text.** Control characters are stripped, every field
is truncated to a bound, and **none of it ever enters a prompt**. It is written to a file for
a person to read. A later feature that wants this text in front of a model is a different
decision and needs its own record.

**Answers are cached in the workspace, and the cache is the point.** Two reasons and both
matter more than speed. A thesis has to be re-buildable: a bibliography assembled from a
cache is assembled from what was actually received, on a date, rather than from whatever the
registry says next year. And a resolved DOI is never asked twice, which bounds the disclosure
above to the DOIs that are genuinely new.

**Preview before anything leaves.** The count of DOIs, the destination, and how many are
already cached, shown and confirmed like every other effect in this system. A person who is
about to tell a third party what two hundred papers they are reading should have to say yes
to that sentence.

## What is measured before building

| | |
|---|---|
| journal names invented by a 14B, asked not to | **12 of 24** (ADR-047) |
| distinct DOIs parsed from the bibliography | **205** (ADR-064) |
| references carrying a recoverable DOI | 225 of 2,315 - **9%** |
| documents whose own DOI could be read | 11 of 23 |

**Nine per cent is the ceiling of this route and it is not a rough edge.** Most bibliographies
do not print DOIs. A work cited by three papers with a DOI in none of them stays invisible to
this, exactly as ADR-064 says. Matching on author and year would widen it and would introduce
the first fuzzy comparison into a project whose checking is exact - a decision to take with a
measurement, not in passing.

## Consequences

- **`lacc resolve <documents>`** takes the DOIs `references` parses and asks the registry
  what each work is. It is a separate command from `metadata`, which reads what a file says
  about *itself* with no network at all - and whose docstring already named this: *"with a
  correct identifier a reference manager resolves journal, volume and pages against a record
  rather than a recollection."* This is that record, reached deliberately.
- A field LACC could not resolve says so. **An empty field is a fact; a filled-in one is a
  claim**, and the whole reason this exists is that a model filled them in.
- The first non-local destination in the project gains an entry in `docs/05-assurance.md`
  under cybersecurity, beside the engine and the notifier.

## Trade-off

**This is a network feature in a local-first project, and calling it anything else would be
dishonest.** The defence is not that nothing leaves - something does - but that what leaves is
a public identifier, that it leaves only when two separate switches are on, only after a
preview, and never more than once per work.

**A registry can be wrong.** Crossref holds what publishers deposited, and publishers deposit
mistakes. This replaces *invented* metadata with *deposited* metadata, which is a different
and better failure: a wrong field here is traceable to a record somebody else published, and
the cache says exactly what was received and when.

**The cache can go stale**, and staleness is this project's most frequent defect - twelve
wrong figures, several of them true sentences that had aged. A cached record therefore
carries the date it was fetched, and the bibliography prints it.
