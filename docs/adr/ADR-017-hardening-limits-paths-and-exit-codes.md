# ADR-017 - Hardening: input limits, path shapes, and honest exit codes

- **Status:** Accepted - not yet implemented (planned for the phase after v0.15.0)
- **Date:** 2026-09-08
- **Context:** Before adding more surface, the existing surface was reviewed against the
  promises PRINCIPLES makes. Four things were wrong. Two were defects rather than
  decisions and were fixed in v0.15.0: an environment variable could send documents to a
  host that was not this machine, and the conversion path wrote files without requiring
  the action to declare `write_files`. The three that remain each change configuration or
  behaviour that is already published, so they are decided here rather than patched.

  The review's negative results are recorded here too. A security check that is not
  written down gets repeated, or worse, assumed.

## Decision

### 1. Input has a size ceiling, and exceeding it is refused rather than absorbed

Nothing in the cycle or the converters looks at how large an input is. A document is
read into memory whole and, for a skill, placed into a prompt whole. A large enough file
exhausts memory, and the failure that follows is a `MemoryError` from somewhere deep in
the process rather than a sentence explaining what happened.

The configuration gains a maximum input size in bytes, applied before a file is read and
before a document is converted. Over it, the run is refused with a message naming the
file, its size and the limit. The default is generous enough that ordinary research
documents never meet it, and it is a real limit rather than a warning: a ceiling that
only prints a message is not a ceiling.

This is deliberately about memory, not about the model. Whether the text fits the
model's context window is a different question with a different answer - detect it, say
so, and later split the document - and it belongs to the phase the roadmap already names.
Solving both with one number would make each of them wrong.

### 2. Paths that are not files are refused at the boundary

The workspace boundary holds against the escapes it was built for: `..`, a `..` hidden
inside a longer path, an absolute path elsewhere, a drive root, a UNC share. Three shapes
pass it that should not, all of them Windows-specific:

- **Reserved device names.** `NUL`, `CON`, `PRN`, `AUX`, `COM1`-`COM9`, `LPT1`-`LPT9`.
  Windows resolves these to devices no matter which directory precedes them, so writing
  a converted document to `NUL` discards it while reporting success.
- **Alternate data streams.** A name containing a colon, such as `notes.md:hidden`,
  writes to a stream that no directory listing shows. LACC's whole posture is that what
  it does is visible; a write that cannot be seen contradicts it.
- The same names with a trailing dot or space, which Windows strips before resolving.

These are refused by shape, in the workspace, next to the containment check. They are not
escapes - each one stays inside the boundary - but containment is not the only promise the
workspace makes. It also promises that a path names a file that can be found again.

### 3. A refused run exits non-zero; a declined run does not

`lacc run` and `lacc ingest` exit 0 when the boundary or a missing capability refuses the
action. A script that checks the exit code is told the work succeeded when nothing ran.
That is the same class of dishonesty as truncating a document and answering anyway.

A refused run exits 1, joining the failures that already do - an unreadable document, an
unsupported format, a destination that exists.

A declined run keeps exiting 0. Nothing failed: the human was asked and said no, which is
the system working. Conflating "you decided not to" with "it broke" would make the exit
code useless for telling the two apart, and confirmation defaulting to no means declining
is an ordinary outcome rather than an exceptional one.

### 4. What was checked and found sound is written down

- **XML external entities in `.docx`.** A `.docx` is a zip of XML, parsed by a library on
  the user's behalf, which is the classic setting for an XXE. A document was built whose
  `document.xml` declared an external entity pointing at a local file, and python-docx did
  not resolve it: the entity came back empty. No mitigation is needed, and the reason to
  record it is that the next person to think of this should read a result rather than
  re-derive one.
- **Boundary escapes.** `..`, `sub/../../`, absolute paths outside, `C:\Windows\...` and
  UNC paths are all refused, and a workspace root given in different letter case still
  resolves and matches. Checked, not assumed.
- **Not verified here: symlink escape.** ADR-003 says a symlink pointing outside the
  workspace is refused, and `Path.resolve` supports that claim. It could not be
  demonstrated on the machine this was reviewed on, because creating a symlink on Windows
  needs privileges the session did not have. The claim stands on the implementation, not
  on a test, and saying so is more useful than implying otherwise.

## Trade-off

A size limit is a number chosen in advance, and every such number is wrong for someone.
Accepted, because the alternative is not "no limit" but "a limit set by available memory,
discovered by crashing". A configured default that a user can raise puts the decision
where it belongs, and the refusal message says what to change.

Refusing paths by shape adds rules to the workspace that are specific to one operating
system, in a module whose other checks are universal. Accepted: the machine LACC runs on
is a real machine, and a boundary that is correct in theory and porous on Windows is not
a boundary. The rules are named and grouped so it is obvious what they are and why.

Changing an exit code changes behaviour that is already published. Accepted, and the
reason it is in an ADR rather than a bug fix: someone may be relying on the current
behaviour, and the change deserves to be findable later.

## Consequences

- The configuration gains a maximum input size; oversized documents are refused with a
  message naming the file, the size and the limit.
- The workspace refuses reserved device names, alternate data streams, and names with
  trailing dots or spaces, alongside the containment check.
- `refused` becomes exit code 1 across the CLI; `declined` stays 0.
- The audit trail lives inside a workspace that is now writable. Ingestion cannot
  overwrite it - creation is exclusive, and the trail exists before any write begins -
  but that is a consequence of ordering rather than a protection anyone designed. Whether
  the trail belongs outside the reachable workspace is left to the decision record on
  running against another machine, where the question becomes sharp.
- Chapter 1 and the CHANGELOG are updated in the phase that implements this.
