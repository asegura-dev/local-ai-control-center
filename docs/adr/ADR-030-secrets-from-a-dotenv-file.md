# ADR-030 - Secrets come from a `.env` beside the configuration

## Status

Accepted.

## Context

ADR-027 decided that secrets are named, not written: the configuration holds the *name* of
an environment variable and the value comes from the environment. The reasoning holds - a
token in a configuration file is a token in every backup of it.

What that decision did not account for is how the value gets into the environment. On
Windows it means `setx` and a new terminal; on Linux, editing a shell profile. It is a
second place to look when something fails, and it is far enough from the configuration file
that the connection between them is easy to lose.

The first person to follow the setup guide wrote the server URL, the topic and a live token
straight into the `*_env` fields. Nothing complained: LACC looked for variables with those
literal names, found none, and reported itself unconfigured. The misreading is entirely
reasonable - the fields sit in a configuration file and look like where values go - and it
put a secret into a file, which is the exact outcome naming the variable exists to prevent.

A design whose protection depends on a step people skip is a design that protects nobody.

## Decision

**A `.env` beside the configuration file supplies the variables it names.**

```
configs/config.yaml     names NTFY_TOKEN      -> safe to commit or share
configs/.env            NTFY_TOKEN=tk_...     -> ignored, never shared
```

The indirection from ADR-027 stays exactly as it was. The configuration still names
variables and still holds no secret; `.env` is a place those variables can come from
besides the shell.

**The real environment wins.** A variable already set is never overwritten, so a server, a
CI job or a deliberate export can override the file without editing it, and `.env` is what
fills the gaps.

**It is read from the directory containing the configuration, and nowhere else.** LACC does
not search upward or try several locations. Guessing which configuration was meant is
precisely what a tool that sends documents somewhere must not do.

**`.env` supplies secrets. It never supplies destinations or permissions.** `network_access`
and `engine_host` stay in the YAML, and this is the load-bearing half of the decision.
ADR-027's rule is that no environment can widen what LACC contacts - the only escape hatch
is a file the user wrote. If a destination could arrive through the environment, an
inherited variable could redirect documents to another machine, and that guarantee would be
gone. So the line is drawn at what the value *is*, not at where it is stored.

**A `*_env` field must look like the name of a variable, in upper case.** This is the check
that would have caught the original mistake, and the upper case is not fussiness: a shape
check alone accepts `tk_f0yn7rfgs48l94eq41y5u7ddh2irw`, which is a valid identifier and
also exactly the thing being guarded against. Case is what separates the name of a variable
from the value of one. The refusal names the field, shows what was given, and says what to
put there instead.

**Its own parser, not a dependency.** `KEY=value` a line, `#` comments, optional quotes, an
optional `export` prefix. Twenty lines, against a dependency present in every environment
LACC runs in.

**Loading reports the names it set, never the values.** So `lacc notify test` can say the
variables were found without printing a token to a terminal that scrolls into a log.

## Consequences

- `load_dotenv` reads a `.env` into the environment without overwriting what is there, and
  returns the names it set.
- The CLI loads it from the configuration's directory before building anything.
- `configs/config.yaml` becomes shareable: it names variables and holds no values.
- `NtfySettings` refuses a `*_env` field that is not an upper-case variable name.
- `.gitignore` matches `config*` at the root by shape rather than by exact spelling, since
  the file that leaked was called `config.yaml.txt`.
- One more place a secret can live, and it is a file. Which is the trade-off below.

## Trade-off

This puts a token back into a file, which is what ADR-027 argued against. Accepted, with
the reasoning narrowed rather than abandoned: what ADR-027 protects is *the configuration*
staying free of secrets, so that it can be copied, shared, committed and backed up like any
other source file. That is preserved exactly. What is added is a second file that is
ignored by git, conventionally understood to be private, and never shared - and which
exists because the alternative was a step people skip, leaving the secret in the
configuration itself.

Being honest about the limit: a `.env` in a synchronising folder is still synchronised, and
a `.env` in a backup is still in the backup. This makes the configuration safe to share. It
does not make the secret safe to store carelessly, and no file-based scheme would.

Requiring upper case refuses a lower-case environment variable, which is legal and
occasionally used. Accepted: the message explains it, renaming a variable costs a minute,
and the case it catches is a live credential written into a file.
