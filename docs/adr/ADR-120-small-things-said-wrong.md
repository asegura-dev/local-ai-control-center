# ADR-120 - The small things the terminal said wrong

## Status

Accepted. The minors of the tests of 25 and 29 September that are the terminal's: D22, D25 and
D26, and five from 25 September. Built on 30 September. The window's minors wait for after the
release.

## Context

None of these loses work, and each sits in a line a person reads for its numbers or its names.

- **A count that did not agree with its word**: *1 sections*, *1 paragraphs*, *1 drafts
  brought in*, *1 entries*, *1 of these are Markdown*, and *1 of 6 stages have nothing
  outstanding*.
- **D25, a doubled period**: *Seifert, Robert; Telli, Tugce; Opitz, Marcel et al.. *Unspecific…**.
  A part ending in its own period - `et al.`, an abbreviated journal - was given another by the
  join.
- **D22, two days for one evening**: at 19:55 on 29 September the copy `bring` made was named
  for the 29th, and the bibliography written a minute later said *Received 2026-09-30*. The
  registry's date was taken in UTC, which was already the next day.
- **The question in the preview of `ask` was cut at sixty characters**: *…with 18F-PSMA-1*. The
  preview is what is agreed to, and part of the question was not in it.
- **Headings cut mid-word by `sections`**: *5.8.5 Recommendat*, *6.3.5 Adjuv*, *6.7.9 Mo*. The
  PDF had broken them - `Recommendat` on one line, `ions for staging of prostate cancer` on the
  next - and the title was read from the first line only. A column of numbers stood beside them
  with nothing to say what they were: the line each section starts on.
- **`lacc --version` did not exist.**
- **D26 - `tools/measure_window.py` checked a line it had written.** The line beside Prepare
  (ADR-106) was never given to the window it opened, so the check that it showed read back a
  sentence the script had set itself.

## Decision

- **A count and its word agree**, through `core/wording.py`'s `counted`, and a verb that follows
  a count agrees with it. The rule of ADR-113 allows `counted` beside the numbers it already
  allowed: it returns a number and a word the program wrote.
- **A part that ends in its own period is not given a second one.**
- **The day a registry answered is this machine's day**, the one the copies are named by.
- **The preview carries the whole question.**
- **A heading broken mid-word is read whole.** When a numbered heading's title ends in a
  lowercase letter and the next line begins with one, the two are joined without a space, as
  long as the result is still short enough to be a title. The listings name their column:
  *line*.
- **`lacc --version` prints the version.**
- **`measure_window` opens the window with the line `lacc window` draws**, and checks that one.

## Consequences

- `tests/test_wording.py`:
  - the count and its word;
  - *1 of 6 stages has*;
  - *et al.* and *Med.* with one period each;
  - the EAU heading joined;
  - the whole question in the preview;
  - `--version`.
- `measure_window`, run against the working workspace: *the line beside Prepare is the one
  lacc window draws: True*.
- The test that asserted *1 drafts brought in* now asserts *1 draft*.

## Trade-off

**The heading rule is a guess about text.** A heading broken at a word boundary rather than
inside a word, with its next line in lowercase, would be joined without the space it needs.
The three headings found were all broken inside a word, and the check that the result still
reads as a title keeps a line of prose from being taken in.

**Only the counts named here were changed.** Others in the program will say *1 things* until
somebody reads them there.
