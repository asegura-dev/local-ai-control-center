# ADR-027 - Reaching machines of your own: a stronger engine, and a notifier

## Status

Accepted.

## Context

Two things v1 needs are the same change. The model has to run somewhere better than this
laptop, because work that gets published cannot come from a three-billion-parameter model.
And a run that takes minutes has to say when it finished, or it will not be used.

Both mean LACC talks to a host that is not loopback, on the user's own private network,
reached over Tailscale.

The project's own documents disagree about whether that is allowed. PRINCIPLES says a
non-loopback host is "real network access and out of scope". VISION says local-first means
not depending on somebody else's cloud, and that "own hardware on an own private network
still qualifies". Both have been true on the page for months; only now does something
depend on which one wins.

## Decision

**Local means not depending on someone else's computer, not staying on one machine.**
PRINCIPLES is amended. A desktop you own, on a network you control, is local in the sense
the project cares about: nothing is entrusted to a third party, and no service can read,
retain or discontinue your work.

**LACC reaches only hosts the configuration names.** The rule that replaces "loopback only"
is not "anything goes when a flag is set" - it is that every destination is written down:

```yaml
network_access: true          # the ceiling, off by default (v0.3.0, first used here)
engine_host: http://desk:11434
notifier:
  ntfy:
    enabled: true
    server_url_env: NTFY_SERVER
    topic_env: NTFY_TOPIC
    token_env: NTFY_TOKEN
    priority: 3
```

`OLLAMA_HOST` keeps its v0.21.0 treatment: an environment variable still cannot send
documents anywhere. A non-loopback engine is reached only when the configuration both
permits network access and names the host, so the escape hatch is a file the user wrote,
not a variable an installer set.

Secrets are named, not written: the YAML holds the *name* of an environment variable, and
the value is read from the environment. A token in a configuration file is a token in a
backup.

**A `Notifier` port with an ntfy adapter behind it.** The port takes a message and reports
delivery; the adapter posts to `{server}/{topic}` with title, priority and tag headers, and
supports bearer or basic authentication. Telegram is not implemented: it is a third party,
and a message telling it that you are working, on what and when, is content about your
research whatever the body says.

**A notification carries no document content.** It says which skill ran, how it ended and
how long it took. Never a prompt, an answer, or the text of anything read. The destination
is a machine the user named, and that is still not a reason to send it work.

**Delivery is best effort and never blocks.** A notifier that cannot reach its server does
not fail a run that already succeeded; the failure is recorded and the run stands.

**The quality gate still forbids reaching the network.** Tests inject the transport, so the
egress guard from ADR-022 stays exactly as it is: LACC gains the ability to reach out, and
the suite still proves that nothing does it by accident.

## Consequences

- `engine_host` and a `notifier` block in the configuration; `network_access` becomes the
  ceiling over both and is off by default.
- `OllamaProvider` accepts a configured non-loopback host; an unnamed one is still refused.
- A `Notifier` port, an `NtfyNotifier` adapter, and `lacc notify test` to check settings
  before relying on them.
- PRINCIPLES changes its network rule; VISION already said this and does not change.
- Notifications record their delivery result in the audit trail like anything else.
- Nothing here makes LACC reach a service it was not told about, and the test suite still
  fails if anything tries.

## Trade-off

Allowing a configured remote host weakens a guarantee that was simple to state. Accepted:
the guarantee was also wrong, and it was blocking the work the project exists for. What
replaces it is narrower than "network access" and stronger than a flag - every destination
is named in a file the user wrote.

Reading secrets from the environment means LACC depends on something outside its own
configuration, which is a second place to look when something fails. Accepted: the
alternative is a credential sitting in a file that gets copied, synced and shared.
