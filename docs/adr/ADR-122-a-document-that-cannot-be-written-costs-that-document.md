# ADR-122 - A document that cannot be written costs that document

## Status

Accepted. Proposed on 1 October 2026, from the first conversion of the thesis's references,
accepted by the user the same day and built once the extraction then running had finished:
that run was using this same code, loaded from the repository.

## Context

`lacc ingest` over the 65 references of the thesis protocol converted 39 documents in 26
minutes. It then ended in a traceback on `lckd.pdf`:
`UnicodeEncodeError: 'utf-8' codec can't encode character '\ud835' ... surrogates not allowed`.

The text extracted from `lckd.pdf` carries 10 lone surrogates. Each is half of a mathematical
alphanumeric symbol (the block that starts at U+1D400), whose other half the extraction did not
deliver. A Python string can hold such a half; UTF-8 cannot encode it.

Four promises broke at once:

- **One document cost the batch.** The 25 documents after it were never converted, though
  `ingest --help` says a failure "costs that document rather than the batch". The batch
  catches `ConversionError` and `PageRangeError`, and this was neither.
- **It ended in a traceback, not a sentence** (ADR-114).
- **The run was left without an end** (ADR-116). It recorded `run_started` and
  `permission_granted`, and nothing after; the Audit section shows it as a crash.
- **An empty file was left behind.** `write_new_file` creates the file for exclusive writing
  and only then writes to it. The write failed after the creation, which left `lckd.md` at 0
  bytes: a document with no text, which also blocked the retry, since LACC writes only to new
  files.

Measured before deciding, with `ingest`'s own converter and writing nothing: none of the 25
pending documents carries a surrogate, and they were then converted by name, 25 of 25 in 8.9
minutes. `lckd.pdf` carries 10 surrogates, all of them lone.

## Decision

1. **A character the extraction delivered in halves is replaced, counted and reported.**
   - Before anything is written, a conversion's text passes through a pure function in a new
     module, `core/surrogates.py`.
   - That function joins a valid surrogate pair into the character it encodes, and replaces a
     lone half with U+FFFD, `�`.
   - The count goes into the run's `document_converted` record and into what `ingest`
     prints: *10 characters arrived in halves and were written as �*.
   - A half is replaced rather than dropped, so the place where something was lost can still
     be found by searching for `�`. Nothing is changed silently, because the converted text is
     what every quotation is checked against.
2. **A file is created only once its text can be written.** `write_new_file` encodes first and
   creates the file second. Text that cannot be encoded raises a `ConversionError` that names
   the file, and nothing is created. The file is still written in text mode, so line endings
   come out as before.
3. **Every failure in a conversion ends its run.** `run_conversion` records `ingestion_failed`
   for any error between reading and writing. For an error it did not expect, the record
   carries the error's type and message. It then raises `ConversionError`, which the batch
   already handles, and the next document goes on.
4. **What the crash left behind.**
   - The empty `lckd.md` was deleted with the user's approval, and `lckd.pdf` is converted
     again once this is in place.
   - The run the crash left open stays open in the trail. The trail only grows, and what that
     run shows is true.

## Consequences

- **`lckd.pdf`, converted again with this in place:** 4 seconds, 33,008 bytes, and the 10
  lone halves written as `�`. `ingest` said so (*10 characters arrived in halves and were
  written as �*), and the run's record carries `halves_replaced: 10`. All 65 references of
  the thesis are text now.
- `tests/test_surrogates.py`, seven tests:
  - a pair is joined into its character;
  - a lone half becomes `�` and is counted;
  - text with none comes back as the same object;
  - `write_new_file` refuses text it cannot encode, and leaves no file;
  - `ingest` of a document whose converter hands over a half writes `�`, says it, and records
    the count;
  - `ingest` of two documents, the first failing in a way nobody wrote a sentence for, converts
    the second, leaves no file for the first, and names its error;
  - that failing run ends with `ingestion_failed`, marked `unexpected`.
- `RunResult` carries `halves_replaced`, so the CLI says it where it happened.
- `src/README.md` names the new module, and `tests/README.md` the new test file.

## Trade-off

**A replacement character changes the text.** A quotation that spans one will not verify. It
would not have verified against text that could not be written at all, and the count says how
many places to look at.

**What was not expected is now caught.** A bug inside a converter ends as one document's
failure, with its type and message, instead of a traceback that stops the batch. It is still
printed and recorded, so it stays visible. The difference is that it no longer stops the other
documents.
