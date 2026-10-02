# ADR-124 - A note per reference, built on verified quotations

## Status

Accepted and built on 1 October 2026. Piloted on three references that day, and closed on 2
October with what the pilot measured.

The first of two records for an idea the user had while the thesis's references were being
converted. The idea has two parts:
- a note per reference, saying how it bears on the thesis, citing its paragraphs, and keeping
  the formulas and whatever else will be needed to write;
- later, LACC itself joining the notes into one body of knowledge, "its own brain". That second
  part is its own record.

**What works and what does not, in one paragraph.** The notes are written end to end, and
every part says what it is: what LACC assembled, what a judge decided, what a model read.
**The verdicts are not yet worth reading.** No model the server holds, measured on the same
pairs, gave verdicts a writer could act on. And the reading model does not keep to the
instruction that separates what a document says from what it means for the thesis. Both are
measured below, and both are left to later records.

## Context

**What exists now.** The thesis's workspace holds:
- the 65 references of the protocol's second version, as text;
- `citas.md`, with 4,447 citable quotations of the 4,844 extracted, each one checked against
  its document (ADR-123);
- the second version's standing context, installed as `contexto.md`.

The references' file names are their keys in the user's `.bib`, so `rokuss.md` is
`[@rokuss]`.

**What a first trial showed.** The skill that already reads a document against the standing
context, `assess_source`, was run on rokuss, hu2020 and hartenstein: 1.2 minutes, 8 quotations,
8 found. It is not the note, for three reasons:
- **It asks a different question.** It reports what is new against the context, and the
  context already summarises these papers, so it answers "overlaps".
- **It is thin.** It gave two or three quotations a paper, without the figures the thesis
  cites them for. Rokuss came without its Dice of 0.517, 0.583 and 0.600, and Hu without 68.1
  against 71.67.
- **A quotation that exists is not one that supports.** Hartenstein's "supports the
  hypothesis" rested on a sentence about heatmaps that does not.

**What the note needs that nothing read until now: the protocol.** The note's sharpest
question is whether each reference says what the protocol cites it for. The protocol cites by
number, `[19]` and `[2-4]`, with a different numbering in the compact version and in the
extended one. The master list, `referencias_maestras.md`, gives each key its numbers in both.
All of this is in the user's folder, outside the workspace.

## Decision

**A note per reference is assembled by LACC, judged where it can be, and read by the model
only where nothing else can.** Each layer is marked as what it is.

1. **What LACC assembles, with no model.** For each key, a new file `notes/<key>.md`, written
   in the markup the user's Obsidian vault reads:
   - **frontmatter:** the key, its number in each version, the DOI, and the reference exactly
     as the master list writes it. Nothing is parsed out of the reference but the DOI: a title
     or a year taken from a formatted string would be a guess;
   - **how to cite it:** `[@key]`, with its numbers;
   - **where the protocol cites it:** every sentence of either version whose `[n]` names this
     key, found by parsing the numbers - a list, a range, a run - and mapping them through the
     master list. A paragraph is split into sentences; **each item of a list and each row of a
     table is a unit of its own**;
   - **its verified quotations** from `citas.md`, each in a `> [!quote]` callout with the page
     the checker found, not the page the model said.
2. **What the judge decides.** Does the reference say what the protocol cites it for?
   - For each citing sentence, its citation marks taken out, the three nearest quotations
     **of that reference alone** are judged: `review`'s machinery, limited to one document,
     and `review`'s four answers - held up, contradicted, not covered, not judged. The
     answer goes beside the sentence, with the quotation it rests on.
   - **Not covered shows the three quotations it judged**, so a reader can tell support that
     was never collected from support collected and judged not to hold. The two call for
     opposite responses (ADR-068).
   - The sentences are Spanish and the quotations English, so they are ranked by meaning
     (`bge-m3`, which asks first, ADR-106).
   - **Which model judges is a line of configuration:** `models: {judge: ...}`, falling back
     to `model` as it always did. It is not a skill, and is routed through the same table so
     that the choice is one line somebody wrote (ADR-051). `review` asks for its judge by the
     same name; `ask --judge` does not change. When the judge's model is not `model`, the
     line before the question says so.
3. **What the model reads, and only it can.** A new skill, `read_for_thesis`, reads each
   reference against the standing context and answers in blocks:
   - **PART:** the label the context itself gives the part of the thesis it bears on - a
     hypothesis, a configuration, a phase, a gap, by the name the context uses;
   - **READING:** what the document itself states, and nothing about the thesis. A quotation
     can support what a document says; it cannot support what the document means for a
     thesis;
   - **QUOTE:** the reference's own words;
   - **PAGE:** where;
   - **USE**, optional: how the thesis might use it. Shown as the model's suggestion and never
     judged, because no quotation of the reference can establish what the thesis should do.

   Each QUOTE is checked as every quotation is (ADR-026), and each READING is judged against
   its QUOTE (ADR-053). A reading whose quotation is not found, or does not support it, is
   kept and marked rather than dropped. The section is headed as the model's reading. English,
   the user's choice: small models write it more reliably, and the quotations are English
   anyway.
4. **Formulas are anchored, never trusted.** A formula is a block whose PART is `Formula`:
   READING is the LaTeX, QUOTE the line of extracted text it comes from. Same labels, same
   parser, same check: the line is checked against the document like any quotation. The LaTeX
   goes in a `> [!warning]` callout, as the model's reconstruction of that line, with the line
   beside it. Extraction breaks formulas (`dkd.md` has `!"#$$%&#"'(=*!'(+,−./`), so nobody can
   check the LaTeX but a person.
5. **The protocol comes in through `bring`.** One file at a time, each after the user sees
   its path (ADR-111): the compact chapters, the extended ones and the master list, from the
   second version's package. **No new reading outside the workspace.**
6. **One command, `lacc notes`.**
   - It takes the references, `--master`, `--against` the corpus, the chapters of each version
     (`--compact`, `--extended`, patterns allowed inside the workspace), and `--into`, by
     default `notes/`. It writes one note per key, never over an existing note: a note already
     there is refused before anything is asked.
   - One preview and one question. It says how many sentences and judgements that is, what
     ranking by meaning sends, and which model reads or judges when either is not `model`. A
     no is recorded and sends nothing.
   - **Its runs:** one `notes` run, whose `readings_judged` record carries a row per judgement
     - the key, whether a sentence or a reading was judged, a sentence's line, the digests of
     the quotation and of what was asked, the verdict - and, under `full`, the judge's
     reasons.
     The reading of each reference is a run of its own, as `collect` reads a document, and
     in passes when the window is known.
7. **A pilot before the 65,** on the references `assess_source` was tried on.

## What the pilot measured

Three references - rokuss, hu2020 and hartenstein - cited by 34 sentences of the protocol:
102 judgements and three readings per run.

**The first pilot, 5.8 minutes.** 0 sentences held up, 6 contradicted and 28 not covered. 7
of the readings' 16 quotations were found, and none was judged to support its reading. Reading
the notes showed four causes:
- the judge, qwen2.5:14b, answered "contradicts" where a quotation merely did not mention the
  sentence - which its own prompt calls `neither`;
- the readings mixed what a document says with what it means for the thesis, which no
  quotation can support, and named parts generically ("Objective", "Hypothesis");
- the protocol's objectives, a list with no blank lines, were read as one sentence citing ten
  works;
- **not covered was mostly honest.** Rokuss's Dice in PSMA and Hu's 68.1 against 71.67 come
  from tables, and `extract_claims` does not quote tables.

**Three changes, then the same references again, 6.0 minutes.** List items became units;
READING was restricted to the document, PART given the context's labels, and the relevance
moved to USE; the judge's model became configurable. Results:
- **sentences:** 0 held up, 8 contradicted and 26 not covered;
- **readings:** 11 of 14 quotations found, none judged to support its reading.

The judge's reasons, kept under `full`, say why:
- **The 14B still answered "contradicts" for quotations its own reasons called silent.** For
  a sentence stating a study's result, a quotation saying only that its authors *assessed
  whether* it could be done was judged a contradiction, while the reason given was that it
  "does not provide any evidence".
- **The readings of rokuss and hartenstein still named parts of the thesis** (a phase, a
  configuration, the main hypothesis), so no quotation could support them. qwen2.5:14b did
  not keep to the instruction; hu2020's readings did.
- **No formula came out.** Where LaTeX was asked for, the 14B wrote "The formula for the
  knowledge distillation loss is provided."

**Five judges on the same pairs.** The same command once for each of four more models on the
server, none larger than 20B - the larger wait for a second card - each named with
`models: {judge: ...}`; the reading stayed with the 14B. The 102 pairs of a sentence and a
quotation were identical in all five runs.

| judge | minutes | seconds a judgement | sentence pairs: follows / contradicts / neither / not judged | readings judged to follow |
|---|---|---|---|---|
| qwen2.5:14b | 6.0 | 2.7 | 0 / 10 / 92 / 0 | 0 of 9 |
| qwen3.5:9b | 4.6 | 1.8 | 0 / 1 / 101 / 0 | 0 of 9 |
| gemma4:12b | 31.7 | 16.5 | 0 / 0 / 102 / 0 | 0 of 9 |
| llama3.1:8b | 2.4 | 0.8 | 71 / 1 / 30 / 0 | 6 of 9 |
| gpt-oss:20b | 2.6 | 0.9 | 0 / 0 / 0 / 102 | none judged |

- **gpt-oss:20b answered nothing in the shape asked**, and every one of its pairs was
  recorded as not judged - what "one failure costs one item" exists for. Why it does not
  answer in shape is not known.
- **llama3.1:8b held up 31 of 34 sentences**, including some whose figures no quotation in the
  corpus carries. It reads as a judge that agrees.
- **qwen3.5:9b and gemma4:12b agreed on 110 of 111 pairs**, nearly all "neither". gemma4:12b
  took nine times as long a judgement; a guess, not measured, is that at a 32k window it does
  not fit the card whole.
- **Agreement does not say which is right.** Twenty pairs, drawn at random by stratum with a
  fixed seed before any new judge had answered, were given to the user to label blind;
  measuring the judges against those labels is the next step, outside this record.
- **The 14B did not repeat its own readings at temperature zero.** The four runs in which
  another model judged between its readings gave the same readings as each other, and
  different ones from the run in which it was the judge as well: 3 of 14 blocks the same
  (chapter 05, "The same prompt gives the same answer").

**What the pairs showed about the protocol.** Its sentences often carry several claims, and a
table row carries three: what a work did, its figures, and what it means for the thesis. One
quotation can hold one of them. And the protocol repeats itself. Read pair by pair on 2
October, 11 of the compact version's 132 sentences and 27 of the extended version's 372
restate a fact said in another paragraph, mostly a summary table repeating the prose; 14 more
of the extended are arguable, such as a hypothesis restated among the expected results. The
pairs came from two rules, neither using a model. **The first rule's count, 13 and 44, was
wrong:** 33 of its 64 pairs shared nothing but the numbers in a tracer's name, such as
`[68Ga]PSMA-11`. A paraphrase that shares no figure and few words reaches neither rule, so
these counts are a floor. Both are for later records: judging a sentence by its claims, and
an editor's pass over what the protocol says twice.

## Consequences

- New code:
  - `core/protocol.py`, pure: the master list, and the sentences that cite by number -
    paragraphs, list items and table rows;
  - `Claim.labels` in `core/grounding.py`: a block keeps its other labels, so PART and READING
    reach the note;
  - `ReadForThesisSkill` in `core/skill.py`, registered as `read_for_thesis`; a skill declared
    in a file cannot use the standing context, so this one is code;
  - `features/notes.py`, which assembles a note and asks nothing;
  - `JUDGE` in `core/config.py`, and the command.

  Tested from the protocol's real shapes (`tests/test_protocol.py`, `tests/test_notes.py`):
  `[2-4]`, `[8, 9]`, `[15, 28, 29]`, a key in one version only, a tracer in brackets that is
  not a citation, a table row, a list with no blank lines.
- **A configuration that names a judge changes `review` too**; one that names none changes
  nothing.
- `tesis.yaml` keeps English. Spanish would have changed every answer in that workspace, not
  only the notes, and the user chose against it. The note's own words are English, as all of
  LACC's are; the protocol's sentences are quoted as written.
- **Not decided here:** which model judges, which waits on the blind labels; whether a sentence
  is judged whole or by its claims; and how to make a reading keep to its document. Until then
  the notes say what they are: a verdict is a judge's, a reading is a model's.
- **Found while documenting this record.** The list of every place LACC writes,
  `docs/stack/files-on-disk.md`, lacked `corpus`, whose output is a new file like every other.
  Chapter 05's count of those places, written with ADR-109, was not updated when `bring`
  arrived the next day. Both are corrected, with `notes` added.
- **Next, by the user's choice on 2 October: an editor's pass over repetition,** before the
  brain.
- Documented with it: the CHANGELOG, chapter 05 (what is written, what is recorded, a judge
  that did not answer, the same prompt, what asks first), `docs/stack/files-on-disk.md`, the
  INDEX, the ADR index, `src/README.md`, `tests/README.md`, `config.example.yaml` and the
  roadmap.

## Trade-off

**Cost, measured.** 34 sentences, 102 judgements and three readings took 6.0 minutes with the
14B judging, and 4.6 with qwen3.5:9b. The time goes with how often the protocol cites a
reference, not with its length. **The 65 wait for a judge worth the time.**

**Judging across two languages.** The 14B's reasons restate the Spanish sentences
correctly, so the language is not what failed; the verdicts are.

**The reading is still a model's reading.** Checking its quotation and judging its support
make it safer to read, not true. It is headed as a reading, and the protocol's own sentences,
with their verdicts, come first in the note.

**The 397 refused quotations are left out** of every note. Some are faithful copies the
checker cannot yet recognise (ADR-123's trade-off). A note built on them would be built on
what nobody can point to.
