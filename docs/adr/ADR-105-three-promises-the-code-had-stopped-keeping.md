# ADR-105 - Three promises the code had stopped keeping

## Status

Accepted. Found on 27-sep by auditing `docs/05-assurance.md` row by row against the source,
while bringing the documentation up to date. Each of the three breaks a rule in PRINCIPLES,
and none had a test that would have said so.

## Context

1. **The question was kept word for word at every audit level.** `audit_level: standard` - the
   default - records what happened and not what was said: the filter drops `prompt` and
   `completion`. But `passages_selected`, written by `lacc ask` and by the window's Ask before
   anything is sent, carried `question` in full, and the filter did not know the key. Under
   the default, every question ever asked of a corpus was in the trail.
2. **`lacc review` asked with yes as the default.** `Read it? [Y/n]` - pressing Enter sent
   every paragraph of a draft to the engine, dozens of judgements. Every other command that
   reaches an engine defaults to no.
3. **`lacc coverage` sent before it asked.** It printed how many topics and quotations it
   would measure, and embedded them in the same breath: the topics and every quotation not
   yet embedded went to the embedding host - which may be another machine - with no question.

## Decision

- **The question is content, and is kept only under `full`.** `question` joins `prompt` and
  `completion` among the keys the filter drops, and both places that record it also record
  its SHA-256, which says *which* question without saying what it was - the rule every
  document in the trail already follows (ADR-023).
- **`review` asks with no as the default**, like everything else that reaches an engine.
- **`coverage` asks before it sends**: how many topics and how many quotations would be
  embedded, by which model, on which host - and `Send them? [y/N]`. Declining sends nothing
  and writes nothing.

**Not decided here, and named so it is not forgotten.** Preparing a question in `ask` and in
the window ranks the corpus, and with `embedding_model` set that embeds the question - which
reaches the engine before the preview that asks whether to send. The preview cannot be drawn
without the ranking, so fixing it is a change to what a preview is, and it gets its own record.
And four commands are not audited at all - `review`, `resolve`, `identify` and `coverage`,
which reach the engine or the network - against "every meaningful execution is audited".
Both are recorded as gaps in `docs/05-assurance.md` until they are closed.

## Consequences

The trail keeps asking questions answerable - which question, when, how many passages - and
stops keeping the question under `standard`. Trails written before this still hold the
questions they held: the chain is append-only, and nothing here rewrites it.

`review` and `coverage` each take one more keystroke to run.

## Trade-off

**A digest is not a question.** Under `standard`, a person reading the trail can tell that the
same question was asked twice, not what it was. That is the point of the level, and `full` is
one setting away.
