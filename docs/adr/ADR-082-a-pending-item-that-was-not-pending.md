# ADR-082 - A pending item that was not pending

## Status

Accepted. A correction to ADR-080, found by reading its own output.

## Context

`lacc status` reported a guideline as **"with no quotation"** while seven sections taken out
of it were collected and in the corpus. It also reported the workspace's own `context_file` -
standing context every run carries - as a document nobody had quoted from.

Neither was true, and a status report that invents pending work is worse than none: it sends
somebody to do a job that is done.

The cause is that an extract does not know where it came from. `sections --take` writes the
part and nothing else, deliberately: hundreds of quotations are checked against these files
as they are, and writing a provenance line **into** one would change a file the corpus points
at (ADR-076).

## Decision

**An extract records its origin beside itself**, in `<name>.md.from.json` - the same shape as
findings beside a report and the registry cache beside a bibliography. A fact *about* the
file, never part of it.

**A document whose extracts are collected is covered through them.** `status` follows the
note back and stops counting the guideline as untouched.

**The configured `context_file` is not a document.** A workspace names it in its own
configuration; counting it as unquoted invents a pending item out of a setting the user
wrote.

## Consequences

- `status` went from three pending documents to one, and the one is a test fixture.
- Extracts taken before this record exist without the note; theirs were written after the
  fact, and say so in the file.

## Trade-off

**The note can be deleted or the extract renamed**, and the link is gone with no error - the
document simply reads as uncovered again. A provenance that lives in a second file is a
provenance somebody can lose, which is the price of not writing into the first one.
