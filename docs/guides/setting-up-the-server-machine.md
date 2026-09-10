# Guide - Setting up the machine that runs the model

A complete walkthrough for turning a computer you own into the machine LACC talks to:
private networking with Tailscale, the Ollama engine, and an ntfy server for
notifications. Written to be followed by someone who has not done any of it before.

Steps are given for **Linux** and for **Windows**. Follow the one your server runs; the
client side at the end is the same either way.

If you are choosing hardware rather than using a machine you already have, read
[what a dedicated machine buys you](a-remote-engine-over-tailscale.md#be-clear-about-what-this-buys)
first - the answer is usually not what people expect.

## What you are building

Three pieces on the server, one line of configuration on your laptop:

```
   your laptop                          the server machine
  +-------------+                      +---------------------+
  |    LACC     | ---- Tailscale ----> |  Ollama  (port 11434)|
  |             | <--- private net --- |  ntfy    (port 8080) |
  +-------------+                      +---------------------+
         ^                                       |
         |            notification               |
    your phone <------------------------ (also on the tailnet)
```

**Tailscale** is what makes the other two safe. It gives every device you enrol a private
address that only your own devices can reach, without opening a single port on your router.
Nothing in this guide is exposed to the internet at any point.

Set aside about 45 minutes. Most of it is downloads.

---

## Step 1 - Tailscale, on every device

Do this first. The addresses it hands out are what everything else is configured against.

Create a free account at [tailscale.com](https://tailscale.com), then install it on the
server, on your laptop, and on your phone.

**Linux:**

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

It prints a URL. Open it, sign in, and the machine joins your tailnet.

**Windows:** download the installer from
[tailscale.com/download](https://tailscale.com/download), run it, and sign in. It lives in
the system tray.

**Phone:** install the Tailscale app from your app store and sign in with the same account.

Now find the server's address:

```bash
tailscale ip -4
```

**Windows:** the same command works from PowerShell, or hover the tray icon.

You get something like `100.101.102.103`. **Write it down - every step below uses it.**
This address is stable: it survives reboots and follows the machine to any network.

Check the connection from your laptop before continuing:

```bash
ping 100.101.102.103
```

If that fails, stop here. Nothing downstream will work, and every later problem will look
like a different problem.

---

## Step 2 - Ollama, bound to the tailnet and nowhere else

This is the step where a mistake matters, so it gets its own explanation.

**Ollama has no authentication of any kind.** No accounts, no tokens, no password. Anyone
who can open a connection to its port can use it and read what you send it. The advice you
will find everywhere is to set `OLLAMA_HOST=0.0.0.0`, which binds it to **every** network
interface the machine has - your home network, your campus network, the café Wi-Fi it joins
next week. Every device on those networks can then send prompts to your engine.

The prompts LACC sends contain the text of your sources. Bind it to the Tailscale address
only.

### Install

**Linux:**

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:** download and run the installer from [ollama.com](https://ollama.com).

### Bind it

**Linux:**

```bash
sudo systemctl edit ollama.service
```

An editor opens. Add these lines in the space it indicates, using *your* address:

```ini
[Service]
Environment="OLLAMA_HOST=100.101.102.103:11434"
```

Save, then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

**Windows:** set a system environment variable named `OLLAMA_HOST` with the value
`100.101.102.103:11434`, then restart Ollama from the tray icon. In PowerShell as
Administrator:

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_HOST", "100.101.102.103:11434", "Machine")
```

Sign out and back in, or restart, for a machine-level variable to take effect.

### Verify it, which matters more than setting it

**Linux:**

```bash
ss -ltnp | grep 11434
```

**Windows:**

```powershell
Get-NetTCPConnection -LocalPort 11434 -State Listen | Select-Object LocalAddress
```

You want to see **your Tailscale address**. If you see `0.0.0.0`, `*`, or `::`, it is
listening on every network and the work is not done. Fix it before continuing.

### A firewall, as a second layer

Worth ten seconds, because a future edit or a changed address can quietly reintroduce the
problem.

**Linux:**

```bash
sudo ufw default deny incoming
sudo ufw allow in on tailscale0
sudo ufw enable
```

**Windows:** in Windows Defender Firewall, ensure no inbound rule allows public access to
port 11434. The Ollama installer does not create one by default; if you added one while
troubleshooting, remove it.

### Pull a model

```bash
ollama pull qwen2.5:7b
```

Which model to choose depends on memory, and if the machine has an NVIDIA GPU, on its VRAM
rather than its RAM. The
[sizing tables](a-remote-engine-over-tailscale.md#if-you-can-build-a-desktop-instead)
have the numbers, including the context cache that people forget to count. If you are
unsure, start with `qwen2.5:7b` - it fits nearly everything and is a large step up from a
3B model.

Confirm the GPU is being used, if there is one:

```bash
ollama run qwen2.5:7b "hello"     # then, in another terminal:
nvidia-smi                        # memory in use means it is on the card
```

A model that quietly ran on the CPU is the most common reason a fast machine feels slow.

---

## Step 3 - ntfy, so a long run tells you it finished

Optional, but the point of a server machine is that you stop watching it.

### Install

**Linux:**

```bash
sudo apt install ntfy
```

**Windows:** run it under Docker Desktop, which is the practical path:

```powershell
docker run -d --name ntfy --restart unless-stopped `
  -p 100.101.102.103:8080:80 `
  -v ntfy-data:/var/lib/ntfy `
  binwiederhier/ntfy serve
```

Binding the published port to the Tailscale address, rather than leaving it as `-p 8080:80`,
is what keeps it off your other networks. The same reasoning as Ollama.

### Configure it, on Linux

Edit `/etc/ntfy/server.yml`:

```yaml
listen-http: "100.101.102.103:8080"
base-url: "http://100.101.102.103:8080"
auth-file: "/var/lib/ntfy/user.db"
auth-default-access: "deny-all"
```

`auth-default-access: deny-all` is the line that matters. Without it, ntfy lets anyone
publish to and read any topic, and the topic name becomes the only thing protecting your
notifications.

```bash
sudo systemctl enable --now ntfy
ss -ltnp | grep 8080          # verify: your address, not 0.0.0.0
```

### Create a user and a token

```bash
sudo ntfy user add --role=admin lacc          # it asks for a password
sudo ntfy token add lacc
```

Under Docker, prefix each with `docker exec -it ntfy`.

Copy the token it prints. It goes in your environment, never in a file.

### Choose a topic nobody can guess

A topic is just a name, and on any server without authentication it *is* the
authentication - whoever knows it can read your notifications and send you fake ones. So
do not call it `lacc`:

```
lacc-tesis-7h3k9x
```

### Subscribe your phone

Open the ntfy app, add a server with your Tailscale address and port, sign in with the user
you created, and subscribe to that topic. **Your phone must have Tailscale connected** to
reach a server bound to the tailnet.

---

## Step 4 - Point LACC at it, from your laptop

Nothing here runs on the server. This is your working machine.

In `config.yaml`:

```yaml
workspace_root: ~/lacc-workspace
model: qwen2.5:7b                          # must exist on the SERVER
context_tokens: 32768

network_access: true                       # the ceiling, off by default
engine_host: http://100.101.102.103:11434  # the destination, named

notifier:
  ntfy:
    enabled: true
    server_url_env: NTFY_SERVER
    topic_env: NTFY_TOPIC
    token_env: NTFY_TOKEN
```

Both `network_access: true` and `engine_host` are required, and they are separate on
purpose: permission and destination are different statements, and LACC contacts a host only
when the configuration makes both.

Then set the secrets in your environment, not in any file:

```bash
export NTFY_SERVER=http://100.101.102.103:8080
export NTFY_TOPIC=lacc-tesis-7h3k9x
export NTFY_TOKEN=tk_...
```

**Windows, PowerShell:**

```powershell
$env:NTFY_SERVER = "http://100.101.102.103:8080"
$env:NTFY_TOPIC  = "lacc-tesis-7h3k9x"
$env:NTFY_TOKEN  = "tk_..."
```

Those last only for the session. To keep them, use `setx` on Windows or add the exports to
your shell profile on Linux and macOS. A token written into `config.yaml` is a token in
every backup and every copy of that folder, which is why LACC has no field for it.

---

## Step 5 - Check each piece separately

Check them in order and stop at the first failure. Each rules out everything before it.

```bash
# 1. the network
ping 100.101.102.103

# 2. the engine answers, and knows the model
curl http://100.101.102.103:11434/api/tags

# 3. notifications arrive
uv run lacc notify test

# 4. the whole thing
uv run lacc run summarize_file paper.md
```

Watch the request land, from the server:

```bash
journalctl -u ollama -f          # Linux
```

---

## When something does not work

| What you see | What it usually is |
|---|---|
| `ping` fails | Tailscale is not up on one of the two devices. Check the tray icon or `tailscale status`. |
| `curl` hangs | Ollama is bound to the wrong address. Re-run the verify command in step 2. |
| `curl` refused | Ollama is not running, or the firewall is blocking. |
| `model not found` | The model is pulled on your laptop, not on the server. Pull it there. |
| `No notifier configured` | One of three things: `network_access: true`, `enabled: true`, or the environment variables in *this* shell. |
| Notification sends, phone silent | The phone is not on the tailnet, or subscribed to a different topic. |
| Answers are slow and the GPU is idle | Ollama fell back to CPU. Check `nvidia-smi` while a run is in progress. |
| A run is refused for prompt size | The document is larger than the window. Raise `context_tokens`, at a cost in memory. |

---

## What this setup does and does not protect

Worth stating plainly, because "local" gets heard as a stronger promise than it is.

- **Your documents leave your laptop.** They go to the engine you named. That is the point
  of the feature, and the reason the host must be written in your configuration rather than
  discovered. Name a machine you own.
- **Tailscale controls who can reach the engine, not what it does.** It is a network, not
  an audit.
- **Ollama still has no authentication inside your tailnet.** Any device you enrol can use
  it. If you share your tailnet with anyone, restrict that port with Tailscale ACLs.
- **Nothing here is exposed to the internet.** No ports are opened on your router, and both
  services refuse anything that is not on the tailnet.

## Now do the thing it was for

With the engine on a machine that can hold a real model, run the check LACC exists to
perform:

```bash
uv run lacc ingest paper.pdf
uv run lacc run extract_claims paper.md
```

Write down how many quotations came back **verified** and how many **not found**. Run the
same document against a smaller model and compare. That number is the only honest answer to
whether the larger model was worth the setup, and it is specific to your sources rather than
to somebody's benchmark.
