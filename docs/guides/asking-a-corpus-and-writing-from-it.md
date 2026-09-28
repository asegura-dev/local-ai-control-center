# Asking a corpus, and writing from what comes back

This guide starts where [running LACC for the first time](running-lacc-for-the-first-time.md)
stops. That one gets a run working against one document. This one is about the thing the
project exists for: turning a folder of papers into paragraphs you can defend.

Everything here was measured on a real bibliography of 24 papers. Where a number appears, it
came from a run, and [chapter 4](../04-measurements.md) says which.

## The shape of the work

    lacc collect    one skill across many documents  ->  a corpus per document
    lacc corpus     several corpora into one         ->  one file of checked quotations
    lacc ask        a question against that file     ->  points, each with its quotation
    --judge         and which readings to look at before citing

Four steps, and only the last two are done more than once. The corpus is built when the
bibliography changes; the asking is the daily work.

## Building the corpus

    lacc collect extract_claims *.md --into corpus.md
    lacc corpus corpus.md other.md --into everything.md

`collect` runs over each document alone, so one that is too large for the window is refused
by name with its token count rather than silently half-read. **Read the refusals**, and then
read those documents in passes - a corpus that does not mention a paper will not mention it
when you ask, and nothing in the answer will say why:

    lacc run extract_claims big-guideline.md --in-passes --pages-per-pass 3

**And use passes on documents that fit, when the document is worth it.** Six papers that fit
the window gave **59 quotations read whole and 352 read in passes** - six times as many, from
the same model and the same documents. The number of quotations is a property of the
**prompt**, not of the document: asked once about nineteen thousand tokens a model answers
with about twenty, and asked five times about four thousand tokens each it answers with about
twenty each time.

What comes back differs in kind, not only in number. Of 103 quotations from one guideline
section, **26 were about the subject being researched against 4** from the single pass - a
pass that sees four pages has no room to summarise and quotes what is in front of it.

It is not free. Passes invent more: the one document measured both ways gave 0 unfound
quotations read whole and 16 of 119 read in passes. The check catches them either way and
marks them, and six per cent of 264 is still far more usable material than none of 59 - but
quote the pair, never the first number alone (ADR-089).

Choose `--pages-per-pass` by **tokens, not pages**. A journal page is about 1,300 tokens and a
two-column preprint page about 320, so the same `3` means very different things. Three to four
thousand tokens per pass is what these measurements used - twelve pages of one document, three
of another.

## How to ask

**Ask for the parts you want, not for the topic.** This is the difference between a useful
answer and a shapeless one, and it is the cheapest thing on this page:

    # shapeless - the model chooses the cut, and it chose radiation dosimetry
    lacc ask "Summarise convolutional networks" --from everything.md

    # what to do instead
    lacc ask "What do convolutional networks contribute to automatic nodal detection on
    PSMA PET/CT: which architectures are used, what performance they reach, and what
    limitations the literature reports." --from everything.md

Three named parts came back as three named parts. A question that names nothing lets the
model decide what you meant.

**Ask in the language you think in.** With `embedding_model` set, a question in Spanish
against an English corpus reached eight relevant passages of the first eight; ranking by
words reached about three, with a ten-year survival figure among them. The answer still comes
back in whatever `output_language` says, which for a thesis in English is English.

**Ask one thing.** Two questions in one sentence get one answer that half-covers both. Run it
twice; a second question against the same corpus takes about three seconds.

**A question with a premise in it gets the premise checked**, and that is a feature. Asked
*why* transformer architectures outperform CNNs here, it answered that the passages do not say
that - rather than assembling a plausible justification out of the passages it had. If you
want the premise tested, put it in the question.

## Reading what comes back

Four things arrive, and each answers a different question.

**`214 passages selected of 777; 563 set aside`** - what the answer is an answer *about*. It
appears before the preview, on purpose: a selection made on your behalf is something to see
before you approve sending it.

**`All 3 quotations are in the passages that were sent`** - the quotations are real. This is
a string comparison, not an opinion, and it is the strongest thing LACC says.

**`2 of 3 readings are worth reading before you cite them`** - a model's judgement about
whether each sentence follows from the quotation under it. Weaker than the line above and it
says so. **Expect most paragraphs to be flagged**: a sentence of prose usually claims a
little more than one quotation establishes, and the flag is a prompt to cite, not an
accusation.

**`could support it: …`** - beside each flagged reading, two passages from what was already
sent that might carry it. Candidates, not support: LACC ranked some sentences and decided
nothing. Use them or ignore them.

### The one rule worth remembering

**Copy the quotations. Rewrite the sentences around them.**

Measured twice on this corpus: quotations verified three of three, readings flagged two of
three. The quotation said *"more sensitive in N-staging"*; the sentence around it said
*"pelvic nodal staging"*. Real, checkable, and narrower than the source supports. That failure
is invisible to a quotation check, because the quotation is always real - which is the whole
reason the judge exists.

## When it says it does not know, believe it

Asked about cost-effectiveness and reimbursement in a country the corpus never mentions, it
answered that the literature provided contains neither, and quoted nothing. Asked for a figure
the corpus holds only for a different tracer, it named the tracer and said the figure for the
one asked about is not there.

That behaviour is the point of the whole project. **When it refuses, the refusal is usually
the correct answer** - and if you think it is wrong, the thing to check is whether the
document is in the corpus at all.

## Narrowing before asking

    lacc corpus everything.md --into nodal.md --about "lymph node, nodal staging, pelvic"

Useful when you know the subject and the rest of the corpus is noise around it. Worth knowing
what it is not: `--about` marks quotations that *mention* those words, and a quotation can be
about a subject without naming it - measured at 51% relevance by keyword and 46% by section
heading, which is why choosing by meaning exists.

## Turning on meaning

    embedding_model: bge-m3     # in your configuration

Off by default: without it nothing changes. With it, the first question against a corpus
spends about 48 seconds embedding it and writes the vectors to a file beside it; every
question after that is about three seconds. The vectors are a cache - delete the file and it
rebuilds.

It matters most across languages and as the corpus grows. At 1,129 citable quotations with a
32k window the budget admits about 220 of them - a fifth - whatever the ranking says, so
what gets in at all is now the ranking's decision (ADR-091). At 777 it was a quarter; the
share falls as you collect more.

## Drafting

`draft` is not built in: it is a skill you declare, in a `skills/` folder beside your
configuration - `configs/skills/draft.yaml` for `configs/yours.yaml`. A declared skill may
only read, and `over: corpus` makes it one you ask a corpus with (ADR-048):

```yaml
name: draft
summary: Draft a passage from checked quotations
over: corpus
instructions: |
  Write continuous academic prose, not a list. Where studies disagree, say so.
fields:
  - name: paragraph
    describe: the prose, three to six sentences
  - name: quote
    describe: one exact sentence from the passages that the paragraph is anchored to
    quotation: true
  - name: source
    describe: the document named beside that passage
```

    lacc ask "<your question>" --from everything.md --using draft --judge

`draft` writes continuous prose instead of a list. Its quotation is the passage the paragraph
is **anchored to**, not the one holding it up - three to six sentences say more than one
sentence can establish, which is why this is the command where `--judge` earns its place.

The loop: draft, read what was flagged, take the candidate that fits or find a better one,
write the sentence yourself.

## Reading your own draft against the corpus

    lacc review chapter.md --against everything.md --into chapter.review.md

The check turned around: paragraph by paragraph, what your corpus holds up, what it
contradicts, and what it does not cover - *not covered* meaning nothing you collected holds
it, which is not the same as wrong (ADR-068). It asks before it sends anything, and no is the
default. The window's *Reviews* section paints the findings over the draft.

## Where the corpus is thin

    lacc coverage topics.md --against everything.md --into coverage.md

One subject per line, and one line starting with `!` that is deliberately outside your
field: the rest are read against it. For each topic, how far the nearest quotation is, and
that quotation printed under it so the number can be checked. **Nothing is called a gap** -
a similarity orders topics, it does not measure an absence (ADR-088). It needs
`embedding_model`, and asks before sending the topics and quotations to be embedded.

## Citing what you use

Metadata comes from the registry that assigns DOIs, never from a model - a 14B asked for
journal names invented twelve of twenty-four (ADR-047). Both switches have to be on in the
configuration: `network_access: true` and `registry_url: https://api.crossref.org`.

    lacc resolve papers/*.md --into bibliography.md
    lacc identify "paper without a DOI.md"
    lacc bib bibliography.registry.json --into new.bib --adding-to yours.bib

`resolve` reads each document's own DOI - from the PDF beside a converted file (ADR-101) -
and says how many it would send, and where, before sending. `identify` lists the DOIs a
document prints and chooses none of them: a paper prints the DOIs of what it cites too.
Name the right one with `--doi`, and it is recorded beside the file. `bib` writes the
answers as BibTeX with no network: keys like `giesel2016`, never one already in the file you
name with `--adding-to`, so what it writes can be appended to it (ADR-102).

## What it will not do

**It will not tell you whether a claim is true**, only whether its quotation is real and
whether the reading follows from that quotation. A paper can be wrong and every check here
will pass.

**It will not choose your subject.** `extract_claims` is deliberately blind to what your
thesis argues, so that knowing what you want to prove cannot make it favour the claims that
fit. Filtering by subject happens after extraction, where you can see what was set aside.

**It will not write your argument.** It brings evidence with its provenance attached. The
paragraph that says what the evidence means is yours, and so is the responsibility for it.
