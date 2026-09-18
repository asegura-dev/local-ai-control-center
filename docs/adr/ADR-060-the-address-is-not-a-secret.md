# ADR-060 - The address is not a secret

## Status

Accepted. Closes the one gap found by the assurance pass in `docs/05-assurance.md`.

## Context

ADR-030 decided where a `.env` may reach:

> **`.env` supplies secrets. It never supplies destinations or permissions.** `network_access`
> and `engine_host` stay in the YAML, and this is the load-bearing half of the decision.

`NtfySettings` had three fields and all three named environment variables: `server_url_env`,
`topic_env`, `token_env`. The first is a **destination**. So a `.env` file - or any environment
variable, set by an installer, a script, or a mistake - decided where a notification went, by
the one route that record forbids, in the record that calls the prohibition load-bearing.

**What travels bounds the damage, and it was designed with that in mind.** A notification
carries the skill's name, the outcome, the elapsed time, counts, and the audit head digest. A
traverse reports *"16 of 24 documents, 431 of 508 quotations in their source"* and never which
documents or which quotations, on the stated reasoning that **how many is less disclosure than
which ones**. No quotation, no document name and no file content has ever left this way.

So what could leak is metadata about research activity rather than research, to somebody who
can already set environment variables on the machine. That is a small hole and it is still the
hole the principle says cannot exist.

**How it survived.** Every check this project has asks a question about code: can this be
reached, is it called, does it cover its call sites. This one is a question about *meaning* -
whether a field named `server_url_env` is a secret or a destination - and nothing mechanical
was going to notice. It was found by reading `PRINCIPLES.md` a line at a time and asking of
each sentence what would have to be true.

## Decision

**The field is split by what each part is.**

| | where it lives | why |
|---|---|---|
| `server_url` | the configuration | a destination, beside `engine_host` |
| `topic_env` | names a variable | on a public ntfy server the topic **is** the access control |
| `token_env` | names a variable | a token in a configuration file is a token in a backup |

**The topic does not move with the address.** It reads like a destination and behaves like a
credential: on ntfy.sh, knowing a topic is what lets somebody read what is published to it.
Moving it into a file that is meant to be shareable would trade one exposure for another.

**The old field is kept, and accepted only in order to refuse it by name.** Deleting it
produces `extra fields not permitted`, which is true and useless. The error now says what
replaces it, where to put it, and that the topic and token stay where they are.

**A variable name written where the address belongs is refused too.** The mirror of the
mistake, and the likelier one: somebody moving a working configuration will reach for
`NTFY_SERVER` out of habit. ADR-027 added the first of these validators because the first
person to follow the setup guide wrote a live token into a field expecting a variable name,
and nothing complained. The same silence is available in the other direction now, so the same
kind of refusal covers it.

## Consequences

- Anyone with a working setup moves one value from `.env` to `lacc.yaml` and is told so by
  name the first time LACC loads the configuration.
- `docs/05-assurance.md` has no gap rows left.
- `NtfyNotifier`'s own scheme check becomes a second line rather than the only one, and its
  docstring says so: the class is public and constructible, so it keeps the check.

## Trade-off

**The address is now in a file people are encouraged to share.** The setup guide says
`configs/config.yaml` can be pasted into a thesis appendix. A tailnet address is not a secret
and does not become one by being written down - but it does say a machine exists at that
address, which a screenshot of a `.env`-based configuration would not have. The alternative is
keeping the destination reachable through the environment, which is what this record exists to
stop.

**A migration error is still an error.** A working installation stops on upgrade until one
line moves. That is the correct trade for the class of change this is, and the message does the
work: it names the new field, the value's new home, and what does not move.
