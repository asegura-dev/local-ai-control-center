# ADR-077 - A line along the bottom

## Status

Accepted. A small feature whose only interesting decision is when *not* to do something.

## Context

The window shows whatever section is open and nothing about the whole. Two questions have no
home: **what is there to work with**, and **can it reach the machine that runs the model**.

The first is a directory listing. The second is a request to another computer, and that is
the difference this record is about.

## Decision

**A bar along the bottom, in two halves.** The left is what is on disk: how many documents,
how many quotations in the largest corpus. The right is what this configuration is *allowed*
to reach - the engine's address, whether the network is on at all, whether a registry is
named.

**The engine is not asked when the window opens.** It is asked when somebody presses
`check`, and the bar says `not checked` until then.

That is the whole decision. A window that pings on opening is a window that talks to the
network **because somebody looked at it** - and this project's first rule is that reaching
anywhere is deliberate. The cost of being wrong here is small and the principle is not: an
interface that quietly makes requests is the thing that makes people stop trusting what a
tool says it does.

**`not checked` and `unreachable` are different words.** A bar that showed a red light for
both would be saying something false half the time - the engine may be perfectly fine and
simply never have been asked.

**The check is passed in, not performed.** `features/status.py` holds the contract
`EngineSeen`; the CLI closes over its configuration and hands the window a function. A view
never touches an adapter, and the layer rule holds without an exception (ADR-066).

## Consequences

- The bar reads the workspace on opening, which is a directory listing plus parsing whatever
  corpora are there. On the real workspace that is one 284 KB file.
- `EngineSeen` carries `asked` as well as `reached`, because the absence of an answer is not
  an answer.

## Trade-off

**A person may read `not checked` as "broken".** The alternative was checking on open, which
trades a wrong impression for an unasked-for request. The wording is the mitigation and it is
not a strong one.

**The count is taken once, when the window opens.** Run `collect` in a terminal while the
window is open and the bar is stale until it is reopened - the same staleness this project
warns about everywhere else, in the one place where re-reading on a timer would mean the
window doing work nobody asked for.
