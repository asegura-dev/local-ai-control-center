# Guide - Setting up the machine that runs the model

Turning a computer you own into the machine LACC talks to. Read Part 1 to know what you are
building, then follow the guide for your server's operating system, then come back for
Part 2.

---

## Part 1 - What you are building

Three pieces on the server, a few lines of configuration on your laptop:

```
   your laptop                          the server machine
  +-------------+                      +----------------------+
  |    LACC     | ---- Tailscale ----> | Ollama  (port 11434) |
  |             | <--- private net --- | ntfy    (port 8080)  |
  +-------------+                      +----------------------+
         ^                                        |
         |             notification               |
    your phone <------------------------- (also on the tailnet)
```

- **[Tailscale](https://tailscale.com)** is a private network between your own devices. It
  is what makes the other two safe: each device gets an address only your devices can
  reach, and **no ports are opened on your router**. Nothing here is exposed to the
  internet at any point.
- **[Ollama](https://ollama.com)** runs the model. It is the reason for the server: a
  machine with memory free can hold a far larger model than a laptop with everything else
  open.
- **[ntfy](https://ntfy.sh)** sends a notification to your phone when a run finishes, so
  you can walk away from a long one.

### What a notification carries

It says **which skill ran, how it ended, and how long it took**. That is the whole message:

```
Title: LACC: extract_claims completed
Body:  extract_claims completed after 1284s
```

Never a prompt, an answer, a file path, or the text of anything read - not even an error
message. The destination is a machine you named, and that is still not a reason to send it
your work.

Delivery is **best effort and never blocks**: a notifier that cannot reach its server does
not fail a run that already produced an answer. The failure is printed and recorded, and
your result stands.

LACC supports ntfy only, and deliberately supports no third-party messaging service. The
reasoning is easy to miss because it is not about the message body: telling a service that
you are working, on what, and at what hour is **information about your research** whatever
the body says. Sending that to a company every day discloses your working pattern and your
subject to somebody who keeps it. A server you run has no such party in it.

Once configured there is nothing to operate: every `lacc run` that completes, is refused or
fails sends one notification, and each is written to the audit trail as `notification_sent`
or `notification_failed` under the same run id as the run it reports. A run you decline
sends nothing - you were at the prompt, so there is nobody to tell.

You need three devices on the tailnet: **the server**, **your laptop**, and **your phone**
if you want notifications.

If you are choosing hardware rather than using a machine you already have, read
[choosing hardware for local models](choosing-hardware-for-local-models.md#be-clear-about-what-this-buys)
first - the answer is usually not what people expect.

---

## Now follow the guide for your server

Each is a single continuous path with nothing to skip over. Pick the one that matches the
machine that will run the model - not your laptop.

### → **[Set up the server on Linux](server-setup-on-linux.md)**

Ubuntu Server and other Debian-based systems.

### → **[Set up the server on Windows](server-setup-on-windows.md)**

Windows 10 and 11.

When you finish, you will have three things written down: the **Tailscale address**, the
**ntfy topic**, and the **ntfy token**. Come back here with them.

---

## Part 2 - Point LACC at the server

Everything from here happens on **your laptop**, not on the server.

### Your documents stay on this machine

Worth stating before anything else, because the natural assumption is the opposite: the
server runs the model, so surely the papers go there too.

They do not. **LACC reads your documents on the machine it runs on**, builds a prompt from
what it read, and sends *that* to the engine. The PDF never leaves your laptop; only the
text inside the prompt travels, and only for as long as the request takes. Your workspace,
your converted Markdown and your audit trail all live here.

This is why the preview says "the contents read above" rather than naming a file. It is
also why `workspace_root` is a path on this machine and the server needs no workspace at
all - the server holds models, and nothing of yours.

### 2.1 Configuration

In `configs/config.yaml`, using your own address. Keeping the remote engine in its own
file - `configs/desk.yaml`, say - is worth doing once you have both: then
`--config configs/desk.yaml` sends work to the server and plain `lacc run` keeps it
here, and which one you used is never a guess.

```yaml
workspace_root: ~/lacc-workspace
model: qwen2.5:7b                          # must be a model you pulled on the SERVER
context_tokens: 32768

network_access: true                       # permission
engine_host: http://100.101.102.103:11434  # destination

notifier:
  ntfy:
    enabled: true
    server_url_env: NTFY_SERVER
    topic_env: NTFY_TOPIC
    token_env: NTFY_TOKEN
```

`network_access: true` and `engine_host` are both required, and they are separate
statements on purpose: one is permission, the other is a destination. LACC contacts a
machine only when the configuration makes both, so nothing it was not told about is ever
reached.

### 2.2 Secrets go in a `.env` beside it, never in the configuration

Create `configs/.env` with the three values you wrote down:

```
NTFY_SERVER=http://100.101.102.103:8080
NTFY_TOPIC=lacc-tesis-7h3k9x
NTFY_TOKEN=tk_...
```

That is all. No `export`, no `setx`, no new terminal.

The split is the point. `configs/config.yaml` **names** the variables and holds no secret,
so you can share it, commit it to your own notes, or paste it into a thesis appendix.
`configs/.env` holds the values and is never shared. Both live in `configs/`, which git
ignores in full.

A variable already set in your shell always wins over the file, so a server or a CI job can
override it without editing anything.

Two things this does not do, said plainly. A `.env` in a synchronising folder is still
synchronised, and a `.env` in a backup is still in the backup: this makes the
*configuration* safe to share, not the secret safe to store carelessly. And `.env` supplies
secrets only - `network_access` and `engine_host` stay in the YAML, because no environment
may decide where your documents go.

If you write a value where a variable name belongs, LACC now refuses the configuration and
says so:

```
`token_env` names an environment variable; it does not hold the value.
Got 'tk_f0yn...', which is not the name of one - they are written in upper
case, like `NTFY_TOKEN`. Put that name here and the value in your environment.
```

---

## Part 3 - Check each piece separately

Run these in order and **stop at the first failure**. Each one rules out everything before
it, which is what turns a vague "it does not work" into a specific answer.

**3.1 The network reaches the server:**

```
ping 100.101.102.103
```

**3.2 The engine answers, and has your model:**

```
curl http://100.101.102.103:11434/api/tags
```

You should get a block of JSON listing the models on the server. If `qwen2.5:7b` is not in
it, you pulled it on the wrong machine.

**3.3 Notifications arrive:**

```
uv run lacc notify test
```

Your phone should buzz.

**3.4 The whole thing:**

```
uv run lacc run summarize_file paper.md
```

To watch the request land, on a **Linux** server run `journalctl -u ollama -f` while it
goes; on a **Windows** server, watch the Ollama tray icon's log window.

---

## When something does not work

| What you see                                   | What it usually is                                                                                                                                                    |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ping` fails                                   | Tailscale is not connected on one of the two devices. Check the tray icon, or run `tailscale status`.                                                                 |
| `curl` hangs and never answers                 | Packets are being dropped, not refused - on Windows that is the firewall. Do step 4 of the Windows guide. On Linux, check the bind address in step 3.                 |
| ntfy answers but the engine does not           | A firewall rule exists for one port and not the other. Docker adds its own when it publishes a port; the Ollama installer does not, because by default it needs none. |
| `curl` says connection refused                 | Ollama is not running, or a firewall is blocking it.                                                                                                                  |
| `model not found`                              | The model is on your laptop, not on the server. Pull it there.                                                                                                        |
| `No notifier configured`                       | One of three things: `network_access: true`, `enabled: true`, or the environment variables not being set in *this* terminal window.                                   |
| Test says sent, phone silent                   | The phone is not on the tailnet, or is subscribed to a different topic.                                                                                               |
| Answers are slow and the graphics card is idle | Ollama fell back to the processor. Check `nvidia-smi` while a run is in progress.                                                                                     |
| A run is refused for prompt size               | The document is larger than the context window. Raise `context_tokens`, at a cost in memory.                                                                          |

---

## What this protects, and what it does not

Worth stating plainly, because "local" gets heard as a stronger promise than it is.

- **Your documents leave your laptop.** They go to the engine you named. That is the point
  of the feature, and it is why the host must be written in your configuration rather than
  discovered. Name a machine you own.
- **Tailscale controls who can reach the engine, not what it does.** It is a network, not
  an audit.
- **Ollama still has no authentication inside your tailnet.** Any device you enrol can use
  it. If you share your tailnet with anyone, restrict that port with
  [Tailscale ACLs](https://tailscale.com/kb/1018/acls).
- **Nothing is exposed to the internet.** No ports are opened on your router, and both
  services refuse anything that is not on the tailnet.
- **Anyone on your tailnet who knows your ntfy topic can publish to it.** They cannot read
  your documents - those never go to the notifier at all - but they can send you messages
  that look like LACC's.
- **Notification titles are folded to ASCII.** HTTP headers are latin-1, so an accented
  character survives as its unaccented form and an emoji becomes `?`. That is deliberate:
  the alternative was an exception, and an exception there would take down a run that had
  already produced its answer.

---

## Now do the thing it was for

With the engine on a machine that can hold a real model, run the check LACC exists to
perform:

```bash
uv run lacc ingest paper.pdf
uv run lacc run extract_claims paper.md
```

Write down how many quotations came back **verified** and how many **not found**. Then run
the same document against a smaller model and compare.

That number is the only honest answer to whether the larger model was worth the setup, and
it is specific to your sources rather than to somebody else's benchmark.

For everyday use afterwards - and for getting your graphics card back when you want it
for something else - see
[running the server day to day](running-the-server-day-to-day.md).
