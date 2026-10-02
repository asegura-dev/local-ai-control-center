# ADR-125 - What a text says twice: an editor's pass, one group at a time

## Status

Accepted on 2 October 2026, and built the same day in three steps: **the finder** (`lacc
repeats`, points 1 and 2 below); after the user read what it found, **the proposals**
(`--propose`, point 3); and, after their pilot, **two more checks and a pointer by chapter**,
which the user chose. Both pilots are in the section on what the proposals showed.

**What the finder showed, on the protocol's own chapters** (2 October, no model, no network):
- the compact version: 5 groups holding 11 of its 132 sentences, read in 4.7 seconds;
- the extended version: 16 groups holding 37 of its 369 sentences, in 6.6 seconds.

The extended version's largest groups are its introduction and the background table both
repeating proPSMA, Fendler, Hartenstein and Trägårdh, and a budget said in three chapters.
Each version's report went to the thesis's workspace as a new file, and each run is in its
trail.

## Context

**The user's request.** Reading the pairs of ADR-124's blind sheet, the user saw that the
protocol repeats itself. They asked for a judge with an editor's eye, doing one narrow piece
of work. Of three shapes offered, they chose this one: LACC finds what is said twice, and a
model, given one group at a time, proposes where the fact stays and how the rest read.

**What ADR-124 measured about broad tasks.** Asked to judge whole sentences against
quotations, the server's models answered nearly everything one way: llama3.1:8b agreed with
nearly all, qwen3.5:9b and gemma4:12b with nearly none. Asked to keep what a document says
apart from what it means for the thesis, the 14B did not. The lesson this project keeps
measuring holds: **what is structure is kept, what is asked for is negotiated.**

**What the protocol repeats, read pair by pair on 2 October.**
- In the compact version, 11 of 132 sentences restate a fact said in another paragraph. In
  the extended version 27 of 372 do, with 14 more arguable.
- Most are a summary table repeating the prose it follows. The extended version's background
  chapter gives Rokuss's Dice, Andrearczyk's, Hu's, Zhou's and Hartenstein's AUC twice each.
- Some are a plan stated in a table and again in prose, or a dataset described in two
  chapters.
- The arguable ones are a hypothesis restated among the expected results, a margin stated in
  a hypothesis and again in the method that tests it.

**What a rule without a model can find, measured against that reading.**
- **A first rule counted 64 pairs, and 39 were not the same fact.** It took any two shared
  numbers for a shared fact, and 33 of its pairs shared only the numbers in a tracer's name,
  `[68Ga]PSMA-11` or `[18F]PSMA-1007`. Two more shared a graphics card's model, one paired two
  different formulas, and three shared round numbers such as 1000 epochs.
- **The rule decided here finds 29 pairs.** By that reading, 21 are the same fact, 8 are
  arguable and none is a different fact. It misses one sure pair: the compact introduction
  restating Hartenstein's finding with none of its figures. It also misses two arguable ones.
  The measuring script found 28. The module counts "only" as an English function word, which
  puts one more arguable pair at exactly half its words: an objective restated in the method.

## Decision

**Finding what is said twice is arithmetic, and LACC does it. Proposing what to do about it
is a narrow task, and a model does it one group at a time. Deciding is the writer's.**

1. **The rule, in a pure module, `core/repetition.py`.**
   - **Units and sentences** are read as `core/protocol.py` reads them: the sentences of a
     paragraph, each list item, each table row. Its two helpers become public and shared, so
     there is one reading of a protocol. Display formulas are skipped.
   - **A specific figure** is a number standing alone that is a decimal, a percentage, or a
     whole number of two or more digits not ending in zero. Years do not count, and neither do
     citation marks, the number of a section, table, figure or phase, or a number that is part
     of a name (`PSMA-11`, `[18F]`, `RTX 5080`).
   - **Content words** are words of four letters or more, or with a digit, outside a short
     list of Spanish and English function words.
   - **Two sentences in different paragraphs or rows state the same fact** when they share
     two specific figures, or one figure and a fifth of their content words, or half their
     content words. Words count only when each sentence has at least eight: two short
     sentences share half their words by accident.
   - Pairs that share a sentence form a group. A group lists its sentences, each with file
     and line, and what they share.
2. **`lacc repeats <files>`, with no model and no network.**
   - It reads only inside the workspace, and prints the groups, largest first.
   - `--into` writes them as a report, a new file and never over one, and the run is recorded
     with the files read and their digests.
   - **It never calls a repetition a defect.** A table that summarises the prose may be what
     a protocol needs. The command says where the same fact is, and nothing more.
3. **The editor's one task, asked for by name: `--propose`.**
   - One call per group, carrying nothing but the group's sentences and their places. The
     answer names:
     - **KEEP**, the place where the fact stays whole;
     - for every other place, **AS**: how that sentence reads without repeating the fact.
       That may be a shorter sentence, a pointer to the place kept, or the sentence unchanged
       when the repetition earns its place.
   - **Checked without a model**, beside each proposal:
     - KEEP and every place named are the group's own;
     - a rewritten sentence adds no figure its original lacked;
     - it keeps its citation marks, or the report names the ones it dropped;
     - it is written in its original's language, judged by its function words;
     - added after the first pilot: it takes out nothing that no sentence of the group still
       says, and it writes no file and no line into the text.
   - **Each proposal is headed as the model's**, under the sentences it would change. The
     user's files are never written: the report is what the writer edits from, in the vault.
   - **One preview and one question** before anything is sent. They say how many groups, and
     so how many calls, and that only the groups' sentences go. A no is recorded.
   - Each call is recorded with the digests of what was sent and what came back, and the text
     only under `full`. The skill is `edit_repetition`, routed through `models` like any other
     (ADR-051).
4. **Built in that order.** The finder first, useful alone and with no engine. Then the
   proposals, piloted on the protocol's two versions, each version on its own. The pilot
   measures:
   - the groups found;
   - each proposal's checks;
   - the time;
   - **the user's reading of each proposal**, which is the measurement that matters.

## What the proposals showed

**The pilot**, on 2 October: `repeats --propose` with qwen2.5:14b, the model `tesis.yaml`
names, over the protocol's 21 groups. The compact version took 0.7 minutes and the extended
1.3, one call per group carrying only that group's sentences.

**Read one by one, the 14B's proposals are not yet an editor's.**
- **One is usable as given:** an objective that now points to the method for its pilot.
- **Seven lose something no sentence of the group says any longer:** the conclusion a
  background paragraph draws, a dataset's mean age, a sentence on what a metric cannot
  measure, the reason given for an expected result.
- **Six point to a place by its file or line,** as "ver línea 29" or a file name with its
  line, two of them among the seven. The model took the labels it was given for its answer as
  references a reader could follow.
- **Several only reword the repeated sentence** and keep its figures, so the repetition stays.
- **One invents:** it names a "sección 8.2" the protocol does not have.

**What the checks saw.** They flagged 10 of the 21. Every pointer by line number was
flagged, because the line was a number its original lacked, and so was one dropped citation
mark. **They did not see the losses as losses.** Of the seven, one was flagged for the
citation mark it dropped and two only for a pointer the same proposal carried; four were not
flagged at all. Checking what a proposal adds cannot see what it takes away.

**The check this calls for, measured but not built:** what a rewrite drops must still be
said by some sentence of the group, once the proposal is applied. Run over the pilot's 21
answers, kept under `full`, it flags 13:
- all seven losses read above;
- two more the reading had missed, both remarks a table carried on what a work showed;
- four rewordings of one or two words, such as "alcanzó" for "mostró".

It shows the words lost, so a synonym is dismissed at a glance. Adding it, and telling the
model which chapter each place is in rather than letting it cite a line, is a change to this
record, for the user to decide.

**Decided by the user the same day, as an amendment to point 3:**
- **a fifth check:** a rewrite loses nothing - no content word, no number - that no
  sentence of the group still says once the proposal is applied. What it loses is listed;
- **a sixth:** a rewrite names no file and no line, which a reader of the text cannot follow;
- **the prompt gives each place its chapter in words**, from its file name
  (`03_antecedentes` is "antecedentes"), and asks for a pointer to name the chapter, never
  the file or the line.

Then the same 21 groups again, to compare.

**The second pilot**, the same model on the same groups, took 0.4 and 0.7 minutes. Read one by
one:
- **No proposal points by file or line** any longer; they say "véase antecedentes" or "el
  capítulo objetivos". The first pilot had six.
- **Nine lose something no sentence of the group still says, and the checks name all nine**,
  with the words lost. Most are the column a table keeps for what a work means to the thesis,
  such as a note that a work is the nearest precedent, taken out as if it were the
  repetition. The checks also name both citation marks a proposal dropped.
- **Two are usable as given**, a table cell that now points to the prose for Ben-Cohen's 28%
  and a plan said once; two more need only their grammar mended.
- **Six flags are synonyms or inflections**, such as "definido" for "definida", which the
  listed words let a reader dismiss.
- **Two pointers were written in square brackets**, a section and its chapter, which a reader
  takes for citation marks. Not checked.

**What this leaves.** The proposals are safe to read: nothing a proposal loses goes unsaid in
the report. They are not yet worth applying unread; the 14B still takes the meaning column
for repetition. A larger model, on the second card, is the next thing to measure.

## Alternatives rejected

- **A model finding the repetition in a chapter.** That is the broad task ADR-124 measured
  failing. Here the finding is arithmetic, and the model is handed one group.
- **Ranking by meaning (`bge-m3`).** It would find the paraphrase the rule misses, but it
  sends every sentence to the engine, and it only ranks: every pair has some similarity. It
  can come later, behind its own question (ADR-106), if the misses prove to matter.
- **Editing the user's files.** The protocol lives in the user's vault, outside the
  workspace, and `drafts/` holds copies. A report leaves the decision, and the writing, with
  the writer.
- **Applying accepted proposals to a new copy**, as `revise_file` writes beside the original
  after its diff (ADR-025). A group can span several files, and nobody has yet seen whether
  the proposals are worth applying. It can come after the pilot.

## Consequences

- New code:
  - `core/repetition.py`, pure - built;
  - the two reading helpers of `core/protocol.py`, made public as `units` and
    `sentences_in` - built;
  - `features/repeats.py`, which assembles the report, asks for one group's proposal through
    the provider port, and checks it - built;
  - the command, `lacc repeats`, with `--propose` - built;
  - `edit_repetition`, the name `models` gives the proposing model (`EDITOR` in
    `core/config.py`). It is not a skill in the cycle, as the judge is not: a model asked one
    narrow thing, one group at a time;
  - `sends` on `IntendedAction`: the preview says "the sentences of each group", not "the
    contents read above", because whole chapters are read and only sentences go;
  - `edits_proposed` in the trail, with a row per group: its places, the place kept, and the
    digests of what was asked and answered. The prompts and answers themselves are kept only
    under `full`.
- Tests built from the protocol's own shapes: tracers' names, `RTX 5080`, `sección 3.4`, a
  percentage, a year, a citation mark, a display formula, and a table row repeating a
  paragraph (`tests/test_repetition.py`, `tests/test_repeats.py`). With the proposals: one
  that adds a figure, one that drops a citation, and one written in English for a Spanish
  sentence.
- `repeats` refuses a PDF or a `.docx` with the sentence `review` already says (ADR-115).
  That sentence ended "review the .md it writes", which named the wrong command for
  `repeats`; it now ends "use the .md it writes".
- Documented with it:
  - the CHANGELOG;
  - chapter 05: what is written, what is audited, what asks first, what reaches the engine,
    and one failure costing one item;
  - `docs/stack/files-on-disk.md`;
  - the INDEX and the ADR index;
  - the READMEs, `config.example.yaml` and the roadmap.
- **Found while documenting it.** Chapter 05 said `measure` records nothing when its preview
  is refused, and that stopped being so with ADR-116, released in v3.0.0. The chapter's own
  row on every run having an end said the opposite. The row now says what is so.

## Trade-off

**The rule was tuned on the text it was measured on.** It was shaped on one protocol and read
by the person writing this record, not by the user. Its precision on other text is not
known, and the pilot is where the user's reading replaces this one.

**It misses paraphrase.** A sentence that restates a finding in other words and without its
figures reaches no rule here.

**A group is a place to look, not a fault.** LACC finds, the model proposes, and the writer
decides. A table that repeats its prose on purpose is left as it is, at the cost of one call
that confirms it.

**Cost.** One call per group. On the protocol the 29 pairs make 21 groups: 5 in the compact
version and 16 in the extended. The pilot measures the time.
