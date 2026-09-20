# ADR-064 - What your papers cite

## Status

Accepted. The measurement that justifies it was taken before the record was written, and it
bounds what this can do more tightly than expected.

## Context

A bibliography of 24 papers is also **2,315 references**, and what those references have in
common is information nobody has looked at. A work that several of your papers cite is one the
field treats as load-bearing, and the useful question is whether you have it.

Two ways to answer it, and they are not equally available.

**Ask a model.** This is the wrong one and it is already measured: asked for the journal a
paper appeared in, with *"say not available for anything missing"* in the prompt, a 14B
invented **12 journal names out of 24** (ADR-047). Reference metadata is exactly the shape of
thing a model will produce plausibly and wrongly, and the reference list is right there in the
document - there is nothing to generate.

**Parse the section that is already in the file.** Measured on the real corpus: **21 of 24
papers yield a parsed reference list**, because their entries are numbered - a structural
anchor rather than a request.

The extraction is mangled in the ways this project already knows how to fix. References wrap
across lines, the typesetter splits words at the break - `Inci -` / `dence` - and a DOI comes
out as `10. 1158/ 1055- 9965`, or worse, split across a newline. `_normalized` rejoins
hyphenated breaks and `_unspaced` removes spacing entirely, both written for quotation
checking, both correct here unchanged.

## Decision

**References are parsed, never generated.** A pure function over the text of a document:
find the reference section, split it into entries on its own numbering, and read what is
structurally present. No model, no network, no permission beyond `read_files`.

**Each reference is folded on its own, not the section as a whole.** This is the defect the
measurement found. `_unspaced` removes newlines with everything else, so a DOI at the end of
one reference runs into the beginning of the next: `10.1158/1055-9965.epi-15-0578` became
`10.1158/1055-9965.epi-15-0578.2.sungh` - reference two, author Sung H. Every DOI came out
distinct because each carried a different tail, and the count of shared works was zero when
the true answer is eight. **Segment first, fold second.**

**A DOI that is a strict prefix of another is dropped.** `10.2967/jnumed` is a truncation of
`10.2967/jnumed.118.224055`, not a work. The rule needs no invented length threshold: if a
longer DOI in the same corpus starts with this one, this one is the broken half of it.

**What it reports is what more than one of your papers cites, and whether you hold it.** The
documents carry their own DOIs in their metadata (ADR-047), so the cross-check is against a
fact the files state about themselves rather than against a filename.

**And it says "not among the ones identifiable by DOI", never "not held".** Measured: 11 of 23
PDFs carry a DOI in their metadata, which is the same figure ADR-047 found. The other twelve
are in the workspace and cannot be compared, so a co-cited work that is one of them would be
reported as missing. Calling that "not held" would be a false negative dressed as a fact - the
shape of error this project has corrected twelve times - so the count of comparable documents
is printed beside the answer.

**It does not reach the network, and that boundary is the decision.** Resolving a DOI to find
out what a work *is* means asking somebody, which means a whitelist, a capability and its own
record. That is deliberately not this. **The question worth most - what do my papers agree is
central, and am I missing it - is answerable with no network at all**, and building the
network half first would have hidden that.

## What was measured before deciding

| | |
|---|---|
| papers whose reference list parses | **21 of 24** |
| references segmented | **2,315** |
| with a DOI that survives folding | **225 (9%)** |
| distinct DOIs, after dropping truncations | **205** |
| works cited by more than one of the papers | **8** |
| the most-cited | 3 papers cite `10.1016/s0140-6736(20)30314-7` |
| documents whose own DOI could be read, to compare against | **11 of 23** |
| of the 8, how many are among those 11 | **none** |

**The three that do not parse were looked at rather than counted as noise.** Two print their
bibliographies in author-year style with no numbering, which is the case this design names as
out of scope. The third numbers its entries with a bare number and no dot - `2 Schroder FH` -
which this could accept and does not, because a continuation line reading *"11 years of
follow-up"* also begins with a number and splitting on that would break the entry above it.

The rule that would settle it is that a bibliography numbers **consecutively**: a bare number
is an entry when it follows the previous one, and part of a sentence when it does not. That is
correct and it is not built, so one paper in twenty-four is currently invisible and this
record says which and why.

**Nine per cent is the honest ceiling of the DOI route.** Most bibliographies do not print
DOIs, and what remains is author, title and year in free text. A first version that only
follows DOIs sees one reference in eleven, and the record says so rather than letting the
figure be discovered later.

## Consequences

- `lacc references <documents>` reports what is cited more than once and what is not held.
- `core/references.py` is a pure module: text in, references out, no I/O and no engine.
- Nothing new is granted. It reads files inside the workspace, like every other skill.

## Trade-off

**Nine per cent coverage is a real limit, not a rough edge.** A work cited by three papers
without a DOI in any of them is invisible to this. Matching on author and year would widen it
and would introduce the first fuzzy comparison in a project whose checking is exact - which is
a decision to take with a measurement, not in passing.

**Counting citations is not judging them.** A work cited by three of your papers may be cited
as the thing they disagree with. This says what is central to the conversation, not what is
right, and the wording says so.

**And the parse will miss reference sections it does not recognise.** Numbered entries are the
anchor; a bibliography in author-year style with no numbering yields nothing. That is
detectable - it reports zero references for that document rather than guessing - and a
document reporting zero is a document to look at rather than a silent gap.
