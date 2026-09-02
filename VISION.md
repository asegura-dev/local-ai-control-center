# LACC Vision

## The north

A local, private, auditable space to work with your own documents through an AI
model - where every action is previewed, confirmed, and recorded. You point LACC at
your files, ask questions, get answers grounded in them, and can leave and come back
to a conversation that remembers where you were. All of it on your own machine, with
no data leaving it and nothing acting without your say-so.

This is not a hosted assistant made local. It is a different bet: control and privacy
over convenience. A frontier chat service is more capable and knows the whole web;
LACC knows *your* documents, runs on *your* hardware, and shows you every step before
it takes it. Its value is not raw capability - it is that you can trust what it did,
because you watched it and it kept a record.

## What it looks like when it arrives

- You keep a set of documents in a workspace LACC is allowed to read.
- You ask a question. LACC reads what it needs (under the `read_files` permission,
  within the workspace boundary), previews what it will do, and asks before doing it.
- A local model answers, grounded in your documents.
- The exchange is auditable, and can be persisted: you close LACC, reopen it, and the
  conversation resumes where it stopped.
- Nothing was sent to a third party. Nothing ran without your confirmation.

## The path there

Each release is one honest step toward that north, not a leap:

- **Read** a single file and summarize it for real.
- **Shape the prompt** - language, instructions, output - so the answer is good, not
  just present.
- **Write** results back to files, with a diff shown before anything is written.
- **Multiple files**, then chunking when they exceed the model's context, then
  retrieval of the relevant parts.
- **Conversation** across turns, then persistence of that conversation.
- **Documentation for adoption**, so someone else can pick it up.

Around v1 the north is met: dialogue with your documents, persisted locally,
documented. Interfaces beyond the CLI (a dashboard), streaming, distributed execution
across your own machines - these come after, on top of a core that already keeps its
promise.

## What it will never become

LACC will not become an autonomous agent, a cloud service, or a system that acts
without the human at its center. Growing more capable never means giving up control -
that trade is the one LACC exists to refuse. The hard rules that guarantee this are
in PRINCIPLES.md.