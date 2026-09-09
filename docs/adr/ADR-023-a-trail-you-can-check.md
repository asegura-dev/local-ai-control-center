# ADR-023 - A trail you can check: hashes where content would expose

- **Status:** Accepted - implemented (v0.22.0)
- **Date:** 2026-09-09
- **Context:** The audit trail answers what LACC did, and two things it cannot answer have
  become visible now that LACC works on real documents.

  It cannot say **which** document. Under `standard` a run records the path it read, and a
  path is a name that outlives its contents: the chapter summarised on Tuesday and the
  chapter at that path today may share nothing. `full` records the text itself, which
  answers the question by keeping a second copy of the private material the whole design
  exists to contain.

  And it cannot say whether the record is intact. The trail is append-only by convention -
  LACC only appends - but nothing about the file resists a line being edited or removed
  afterwards. A record that can be silently changed answers "what happened" only as well as
  whoever last had the file wanted it to.

  Both are traceability problems, and the same instrument answers them.

## Decision

### 1. A digest identifies a document; the content stays where it is

Every file the cycle reads is recorded with the SHA-256 of its contents alongside its path,
at every audit level. A digest is not the material: it cannot be read back into a thesis,
and it is exactly enough to prove that the file summarised then is or is not the file at
that path now.

This is the shape the project's own principle asks for. Traceability wants to know which
document; exposure is what storing the document costs. A hash gives the first without the
second, so `standard` stops being a level that trades away the ability to check.

The prompt and the completion are recorded by digest too, for the same reason: under
`standard` the trail can now prove which prompt produced which answer, and a `full` record
kept elsewhere can be checked against it.

### 2. The trail is hash-chained, following the pattern this author already chose

Each record folds the previous record's digest into its own: `SHA256(record + previous)`.
Any after-the-fact edit breaks the chain from that record onward, so tampering stops being
silent and becomes locatable to a position in the file.

The design is taken from NetGuard's ADR-003 rather than invented here. That decision
weighed a single-file checksum - which detects that something changed but not where, and
loses ordering - and cryptographic signatures, which are stronger and bring key management
to a tool that deliberately has no operational story. The same reasoning holds, and reusing
a decision the author has already made and lived with is better than making a parallel one.

### 3. `lacc verify` walks the chain and says where it breaks

A trail that could be checked and never is provides assurance rather than evidence. The
command reads the file, recomputes the chain, and reports either that it holds or the first
record where it does not.

Records written before this release carry no digest. They are reported as unverifiable,
not as tampered: the trail cannot vouch for what predates the mechanism, and saying so is
the honest reading rather than raising an alarm about ordinary history.

### 4. What the chain does not defend against is stated plainly

It detects modification by anything that does not know the file is a chain - an editor, a
sync conflict, a careless script, a person removing an inconvenient line. It does **not**
defend against a deliberate, informed rewrite: anything with write access to the file can
recompute every digest from the point it changed and produce a chain that verifies.

Closing that needs a key the trail is signed with and somewhere to keep it, which is an
operational story this project has repeatedly declined. So the property claimed is
"silent tampering becomes detectable", and no more than that. Overstating it would be worse
than not having it, because a trail believed to be stronger than it is gets relied on where
it should not be.

The related question - whether the trail belongs outside a workspace that is now writable -
stays where ADR-017 left it, for the decision record on running against another machine,
where it becomes sharp.

### 5. Hashing is not optional, and not configurable

No level turns it off. It costs a read of a file LACC is about to read anyway and a digest
of a string it already holds, and an audit level that could disable the integrity of the
audit would be a setting whose only use is making the record less trustworthy.

## Trade-off

Every record grows by two digests and a chain link, and the file grows faster. Accepted:
a few dozen bytes per record, against a trail that can be checked.

Hashing file contents means reading them to hash - already happening for the read path, and
a second pass for ingestion, where the source is read by the converter rather than by LACC.
Accepted rather than plumbed around: the alternative is threading a digest out of every
converter to save one read of a file already in the page cache.

The chain makes an audit file harder to edit legitimately. Accepted, and intended: there is
no legitimate edit. A trail is appended to or it is replaced.

## Consequences

- Every audit record carries the digest of the record before it, so an edit breaks the
  chain from that point on.
- Files read or converted are recorded with the SHA-256 of their contents at every level;
  prompts and completions are recorded by digest at every level, and by content only under
  `full`, as before.
- `lacc verify` reports whether the chain holds and, if not, where it first breaks.
- Records predating this release verify as unverifiable rather than as broken.
- The property claimed is that silent tampering becomes detectable, not that tampering
  becomes impossible.
- Chapter 1 and the CHANGELOG are updated in this phase, and the documentation that had
  fallen behind - the chapter index listing one decision record of twenty-two, and a
  development chapter describing a quality gate that is no longer the one that runs - is
  brought up to date with it.
