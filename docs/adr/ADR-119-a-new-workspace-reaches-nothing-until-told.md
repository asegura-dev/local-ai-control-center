# ADR-119 - A new workspace reaches nothing until somebody writes that it may

## Status

Accepted. Found on 25 September, and decided by the person on 29 September: *the ideal would be
for it always to be false by default*. Built on 30 September.

## Context

The window's Workspaces section writes a new configuration and a folder for it (ADR-093). It
wrote the new configuration by carrying over what makes an engine reachable from the one in use.
From a configuration that reaches the engine on another machine, that meant
`network_access: true` and the host.

So the new workspace was granted the network. It was shown before it was written, but nobody
decided it for that workspace. Meanwhile the window's Configuration section says
`network_access` is not changed from the window: it is a refusal being lifted rather than a
setting, and a toggle is not a deliberate decision (ADR-094). One section wrote what the other
said the window does not write.

The principles say permissions are restrictive by default and a configuration removes and
never grants. A configuration written by the program on its own initiative is the one place a
grant could appear that no person wrote.

## Decision

**A configuration written by the window says `network_access: false`**, whatever the one it
was made from says.

**The engine it came from is named, not dropped.** When the source reaches a host on another
machine, the host is written as a comment beside the switch:

```yaml
network_access: false
# The configuration this was made from reaches an engine at http://100.76.182.73:11434.
# To reach it from this workspace too, change the line above to true and remove
# the # below. The window does not grant it.
# engine_host: http://100.76.182.73:11434
```

Granting it is two edits a person makes in the file, which is where every other grant is made.

**A host on this machine is carried as it is.** Without the network, a host that works is a
local one, and there is nothing to grant.

What else is carried is unchanged: the model, the window, the embedding model, the registry
address, and a full audit level.

## Consequences

- A workspace made from `denso.yaml` opens with its engine unreachable until
  `network_access: true` is written. The Engines section says why: *network_access is off, so
  only this machine is reachable*.
- The test that asserted `network_access: true` was carried now asserts the opposite, and says
  why.
- New tests:
  - the written file loads with the network off and no remote host;
  - a local host is carried as written.

## Trade-off

**A workspace made to work at once now needs a line written first.** For this project that is
the ordinary case, since the engine is on another machine, and the line is named in the file it
goes in. The alternative was a permission the window granted, which the window says it does
not do.
