# ADR-115 - What review could not judge, and what it could not read

## Status

Accepted. Four findings of the test of 29 September - D3, D4, D17 and D20 - and two more found
while writing the tests for them; built on 30 September.

## Context

`review` reads a draft against the corpus and says, paragraph by paragraph, what holds it up.
It is the command the writing stage leads to, and the one a person runs on their own thesis.
The test found that it could say something false about that thesis in four ways.

- **D3 - an engine that did not answer was reported as a corpus that does not hold the
  paragraph.** On the same draft, *1 held up* with the engine running became *0 held up,
  1 not covered* with it stopped. The run exited 0, and nothing said the judge had not
  answered. The judge already turned a failed call into `undecided`, and `review` then
  counted `undecided` as `nothing`. A test asserted exactly that. The engine shares a card
  with training, so a model that does not load is the ordinary case, not the rare one.
- **D4 - a `.docx` or a PDF was read as text.** The step right after `bring` is `review`, and
  a Word file is a zip. Its first "paragraph" began `PK…[Content_Types].xml`, and the preview
  offered to send sixty-nine judgements of it.
- **D17 - text that is not UTF-8 was read with replacement marks**, and sent to be judged as
  `Dise?o metodol?gico`, without a word.
- **D20 - a no ended with 1 and no sentence**, where `bring` and `ask` say *Declined* and end
  with 0.

Two more were found by the tests written for these:

- **A configuration naming no model ended in a traceback after the yes**, with the run open in
  the trail. The judge was built after the question.
- **A corpus of one quotation left its paragraph "not covered" without asking the judge
  anything.** The budget meant to hold every quotation counted each quotation's text but not
  its note, while the ranking counts both, so the last quotations never fit. On the working
  corpus the three nearest always fit and nothing changed. On a small corpus, the one
  quotation that mattered did not.

## Decision

- **`undecided` is a verdict of its own.** A paragraph is not judged when the judge did not
  answer for one of the quotations nearest to it and none held it up or contradicted it.
  Without that answer, "nothing holds this" is something nobody knows.
  - It is counted apart, and printed apart: *N not judged: the engine did not answer*.
  - The report gives it its own section, before the uncovered ones.
  - The window paints it faint, and says *not judged - the engine did not answer*.
  - The findings file carries it.
  - When nothing at all was judged, the command ends with 1.
- **A draft is text, or it is refused before the question**:
  - a `.docx` or a PDF is sent to `lacc ingest` first, with the command to run;
  - bytes no text file holds are refused;
  - text that is not UTF-8 is refused, with the byte and where it is.

  A byte-order mark is dropped, since it is not part of the draft.
- **A no is said and ends with 0**, as it does in `bring` and `ask`.
- **The judge is built before the question**, and a configuration naming no model is refused
  there, with no run opened.
- **The budget counts what the ranking counts**: each quotation's text and its note.

## Consequences

- The tester's case, driven through the CLI against an engine that does not answer: *1 not
  judged*, *0 not covered*, exit 1, and the findings file says `undecided`. It is also the
  test for the budget: with the budget as it was, that paragraph was never judged, and the
  test failed.
- Tests:
  - a candidate left unjudged leaves its paragraph unjudged;
  - the report names *not judged* apart from *not covered*;
  - `.docx`, PDF, NUL bytes, Latin-1 and a byte-order mark, each read or refused as above;
  - a draft with no model named, refused before the question with nothing in the trail;
  - a declined review, said and ended with 0.
- The test that asserted `undecided` became `nothing` now asserts the opposite, and says why.
  The CLI's own review fixtures name a model, since the judge is built before the question.

## Trade-off

**Not judged is not retried.** A paragraph left unjudged stays so until the review is run
again; nothing here asks the engine a second time. That is the right default for an engine that
is off, and the wrong one for a single dropped call. Which one happened is not visible from
here.

**Refusing Latin-1 asks the person to re-save a file.** Guessing the encoding would read most
Spanish text correctly and some of it wrongly, and nothing would say which.
