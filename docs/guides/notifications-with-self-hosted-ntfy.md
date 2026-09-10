# Guide - Notifications when a run finishes

Once the model is large enough to be worth using, runs get long enough that you stop
watching them. LACC can push a notification to your phone when one finishes, through an
[ntfy](https://ntfy.sh) server you host yourself.

## What LACC sends, and what it never sends

A notification says **which skill ran, how it ended, and how long it took**. That is the
whole message:

```
Title: LACC: extract_claims completed
Body:  extract_claims completed after 1284s
```

It never carries a prompt, an answer, a file path, or the text of anything read - not even
an error message. The destination is a machine you named, and that is still not a reason
to send it your work.

**Delivery is best effort and never blocks.** A notifier that cannot reach its server does
not fail a run that already produced an answer. The failure is printed and written to the
audit trail, and your result stands.

## Why self-hosted, and why not a messaging app

LACC supports ntfy only, and deliberately supports no third-party messaging service.

The reasoning is easy to miss, because it is not about the message body. A message telling
a service that you are working, on what, and at what hour is **information about your
research** whatever the body says. Sending "extract_claims finished" to a third party
every day discloses your working pattern and your subject to a company that keeps it. For
private research that is the same category of leak as the content itself, only slower.

A server you run, reached over your own tailnet, has no such party in it.

## Setting up the server

Installing ntfy, binding it to your tailnet, creating a user and issuing a token are in
[setting up the server machine](setting-up-the-server-machine.md#step-3---ntfy-so-a-long-run-tells-you-it-finished),
alongside the engine setup, for Linux and for Windows.

One line from it is worth repeating here because everything else depends on it:
`auth-default-access: "deny-all"` in the server configuration. Without it, ntfy lets anyone
publish to and read any topic, and the topic name becomes the only thing protecting your
notifications.


## Choose an unpredictable topic

On a server with `deny-all` and a token, the token is your authentication. On any server
without it, **the topic is the authentication** - anyone who knows it can read your
notifications and publish to them.

So do not call it `lacc`. Call it something nobody guesses:

```
lacc-tesis-7h3k9x
```

LACC has no configuration field that could hold the topic, and that is on purpose. The
configuration holds only the *name* of an environment variable to read it from, so there
is no field to accidentally commit. A guard that merely warns about a secret in a
versioned file is the guard that eventually gets ignored; a field that does not exist
cannot be filled in.

## Configuring LACC

In `config.yaml`:

```yaml
network_access: true    # the ceiling over this, as over the engine
notifier:
  ntfy:
    enabled: true
    server_url_env: NTFY_SERVER
    topic_env: NTFY_TOPIC
    token_env: NTFY_TOKEN
    priority: 3
    tags: []
```

And in your environment, not in any file that gets committed or synced:

```bash
export NTFY_SERVER=http://100.101.102.103:8080
export NTFY_TOPIC=lacc-tesis-7h3k9x
export NTFY_TOKEN=tk_...
```

A token written into a configuration file is a token in every backup of that file, in
every copy of the folder, and in the repository if the file is ever added. Naming the
variable costs one line and removes the whole class of accident.

## Check it before relying on it

```bash
uv run lacc notify test
```

This sends one notification and reports what happened. It exits non-zero when nothing was
delivered, so it is usable from a script.

Getting `No notifier configured` means one of three things is missing, and they are
separate on purpose: `network_access: true`, `notifier.ntfy.enabled: true`, or the
environment variables actually being set in the shell you are running from.

Install the ntfy app on your phone, add your server's address, subscribe to the topic, and
run the test again. Your phone must be on the tailnet to reach a server bound to it.

## After that

Nothing more to do. Every `lacc run` that completes, is refused, or fails sends one
notification, and each is recorded in the audit trail as `notification_sent` or
`notification_failed` under the same run id as the run it reports. A run you decline sends
nothing - you were at the prompt, so there is nobody to tell.

## Known limits

- **Titles are folded to ASCII.** HTTP headers are latin-1, so an accented character
  survives as its unaccented form and an emoji becomes `?`. This is deliberate: the
  alternative was an exception, and an exception here would take down a run that had
  already produced its answer.
- **Anyone on your tailnet who has the topic can publish to it.** They cannot read your
  documents - those never leave for the notifier - but they can send you notifications
  that look like LACC's.
- **Only ntfy.** There is no plugin system for notifiers. Adding a second transport would
  mean writing a second adapter behind the same port, which is a small change but a
  deliberate one.
