# LACC Vision

## The north

A local, private place to write from your own sources - where the work is grounded in
documents you chose, every quotation is checked against the document it claims to come
from, and anything the model produced without support is marked as such.

You keep your references in a workspace. You ask for a summary, a critique, a revision, an
extraction of what a paper actually claims. What comes back is text you can use, with its
claims traceable to a page. All of it on hardware you own, with nothing sent to a third
party and nothing acting without your say-so.

This is not a hosted assistant made local. It is a different bet: a frontier chat service
is more capable and knows the whole web, and it will also produce a citation that does not
exist, in prose confident enough that you will not check. LACC knows only *your*
documents, runs on *your* hardware, and its central promise is not fluency - it is that
what it hands you can be verified, because it verified what it could and flagged what it
could not.

For work that gets published, that trade is not a compromise. An invented reference in a
paper is not an inconvenience; it is the kind of mistake that follows a name around.

## What it looks like when it arrives

- Your references live in a workspace LACC is allowed to read. PDFs and Word documents are
  converted to text you can open and correct, deliberately, rather than parsed invisibly.
- You ask what a source claims. What comes back carries quotations and page numbers, and
  **LACC has checked that each quotation appears in the document** - what it could not find
  is reported as unsupported rather than presented as fact.
- You ask for a revision of a passage. You see the difference before anything is written,
  and what is written goes beside the original, never over it.
- The model runs on a machine of your own - the laptop in front of you, or a stronger one
  on your own private network. Both are local: what "local-first" refuses is depending on
  somebody else's cloud, not using a second computer you own.
- Every run was previewed, confirmed and recorded, in a trail whose records are chained so
  that a silent edit becomes detectable.
- Nothing left the machine. Nothing ran without your confirmation.

## The path there

Each release is one honest step, not a leap. Much of this is done:

- **Read** a file and summarize it for real. *(v0.13.0)*
- **Shape the prompt** so the answer is good, not just present. *(v0.14.0)*
- **Ingest** the formats real sources arrive in. *(v0.15.0)*
- **Refuse rather than mislead**: an input too large, a prompt the model cannot hold, a
  workspace that could be published, a trail that was altered. *(v0.16.0 - v0.23.0)*
- **Write** results back beside the original, with a diff shown first, and read several
  documents at once. *(v0.24.0)*
- **Ground what is produced**: quotations with pages, verified against the source, and
  anything unsupported marked.
- **Run against a stronger machine** of your own, over a private network.
- **Say when a long run has finished**, through a notifier you host yourself.
- **Documentation for adoption, and a project that can be cited**, so the work can be built
  on by someone else.

v1 is met there, and deliberately not further. Working with a whole library rather than a
handful of sources, holding a conversation across turns, letting the model choose what to
do next - these are real and they are v2. A smaller v1 that is true beats a larger one that
is late.

## What it will never become

LACC will not become an autonomous agent, a cloud service, or a system that acts without
the human at its center. Growing more capable never means giving up control - that trade is
the one LACC exists to refuse. It will also not become a tool you have to trust: whatever
can be checked by machine is checked, and whatever cannot is labelled. The hard rules that
guarantee this are in PRINCIPLES.md.
