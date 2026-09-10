# Guide - Setting up the server machine, on Linux

Follow these steps in order on the machine that will run the model. Written for Ubuntu
Server 22.04 or newer; other Debian-based systems work the same way.

If your server runs Windows, use [the Windows guide](server-setup-on-windows.md) instead.
For what you are building and why, see
[setting up the server machine](setting-up-the-server-machine.md).

Everything here is typed into a terminal on the server. If the machine has no screen,
connect to it over SSH first.

Set aside about 45 minutes. Most of it is downloading.

---

## Step 1 - Join the machine to your private network

[Tailscale](https://tailscale.com) gives every device you enrol a private address that only
your own devices can reach. No ports are opened on your router, and nothing here is exposed
to the internet.

**1.1** Create a free account at [login.tailscale.com](https://login.tailscale.com/start).

**1.2** Install it on the server:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

**1.3** Connect it:

```bash
sudo tailscale up
```

It prints a URL. Open that URL in any browser, sign in, and the machine joins your network.

**1.4** Find the address it was given:

```bash
tailscale ip -4
```

You will see something like:

```
100.101.102.103
```

**Write this down.** Every remaining step uses it, and everywhere this guide shows
`100.101.102.103` you type your own. The address is stable: it survives reboots and follows
the machine to any network it later joins.

**1.5** Install Tailscale on your laptop and on your phone too, signing in with the same
account. Downloads are at [tailscale.com/download](https://tailscale.com/download); the
phone apps are in the [App Store](https://apps.apple.com/app/tailscale/id1470499037) and on
[Google Play](https://play.google.com/store/apps/details?id=com.tailscale.ipn).

### Checkpoint

From your **laptop**, run:

```bash
ping 100.101.102.103
```

You should get replies. **If you do not, stop here.** Nothing after this point can work,
and every later problem will look like a different problem. Check that Tailscale shows as
connected on both devices.

---

## Step 2 - Install the engine

[Ollama](https://ollama.com) is what actually runs the model.

**2.1** Install it:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**2.2** Confirm it is running:

```bash
systemctl status ollama
```

Look for `active (running)`. Press `q` to exit.

---

## Step 3 - Restrict the engine to your private network

**Do not skip this step.** Ollama has no accounts, no passwords and no tokens of any kind.
Anyone who can reach its port can use it and read what you send it, and the prompts LACC
sends contain the text of your documents.

Most instructions on the internet say to set `OLLAMA_HOST=0.0.0.0`. That makes it listen on
**every** network the machine is connected to - your home network, your office network, any
Wi-Fi it joins in future. Bind it to the Tailscale address instead, so only your own
devices can reach it.

**3.1** Open the service configuration:

```bash
sudo systemctl edit ollama.service
```

A text editor opens with a mostly empty file and a comment marking where to type.

**3.2** Add exactly these two lines above the marked area, using **your** address:

```ini
[Service]
Environment="OLLAMA_HOST=100.101.102.103:11434"
```

Save and close. In the default editor (nano) that is `Ctrl+O`, `Enter`, then `Ctrl+X`.

**3.3** Apply it:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

### Checkpoint - verify, do not assume

This check matters more than the setting, because a typo leaves it listening everywhere and
nothing warns you.

```bash
ss -ltnp | grep 11434
```

You should see **your Tailscale address**:

```
LISTEN 0  4096  100.101.102.103:11434  0.0.0.0:*
```

If instead you see `0.0.0.0:11434` or `*:11434`, it is still listening on every network.
Go back to 3.2, check the address for typos, and repeat.

---

## Step 4 - Add a firewall

Ten seconds of work, and it protects you if a future edit or a changed address reintroduces
the problem.

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow in on tailscale0
sudo ufw allow ssh
sudo ufw enable
```

`sudo ufw allow ssh` matters if you are connected over SSH - without it, enabling the
firewall disconnects you.

Confirm:

```bash
sudo ufw status
```

---

## Step 5 - Download a model

```bash
ollama pull qwen2.5:7b
```

This downloads several gigabytes.

`qwen2.5:7b` is a safe starting point: it fits almost any machine and is a large step up
from a 3B model. If your server has plenty of memory, or an NVIDIA graphics card, the
[sizing tables](choosing-hardware-for-local-models.md#if-you-can-build-a-desktop-instead) say
what else will fit - remembering that the context window takes memory too, which is the
part people forget.

**5.1** If the machine has an NVIDIA card, confirm the model is actually using it. Start a
model in one terminal:

```bash
ollama run qwen2.5:7b "hello"
```

and while it answers, in a second terminal:

```bash
nvidia-smi
```

Memory in use under `ollama` means it is running on the card. If the card is idle, the model
is running on the processor instead, which is the most common reason a fast machine feels
slow.

---

## Step 6 - Install ntfy for notifications

Optional, but the reason for a server machine is that you stop watching it. Skip to
[pointing LACC at the server](setting-up-the-server-machine.md#part-2---point-lacc-at-the-server)
if you do not want notifications yet.

**6.1** Install it:

```bash
sudo apt update
sudo apt install ntfy
```

**6.2** Open its configuration:

```bash
sudo nano /etc/ntfy/server.yml
```

**6.3** Find these settings and set them to the following, using your address. Most lines in
the file are commented out with `#`; remove the `#` from the ones you change.

```yaml
listen-http: "100.101.102.103:8080"
base-url: "http://100.101.102.103:8080"
auth-file: "/var/lib/ntfy/user.db"
auth-default-access: "deny-all"
```

`auth-default-access: "deny-all"` is the important one. Without it, anybody who can reach
the server can read and send notifications on any topic.

Save with `Ctrl+O`, `Enter`, `Ctrl+X`.

**6.4** Start it:

```bash
sudo systemctl enable --now ntfy
```

**6.5** Verify the address, as with Ollama:

```bash
ss -ltnp | grep 8080
```

Again, your Tailscale address and not `0.0.0.0`.

**6.6** Create a user. It will ask for a password:

```bash
sudo ntfy user add --role=admin lacc
```

**6.7** Issue a token:

```bash
sudo ntfy token add lacc
```

It prints something starting with `tk_`. **Copy it now** - it is shown once. It goes into
an environment variable later, never into a file.

**6.8** Choose a topic name. A topic is just a label that groups notifications, but treat it
as a secret: pick something nobody would guess.

```
lacc-tesis-7h3k9x
```

Not `lacc`. Write it down next to the token.

**6.9** On your phone, install the ntfy app from the
[App Store](https://apps.apple.com/app/ntfy/id1625396347) or
[Google Play](https://play.google.com/store/apps/details?id=io.heckel.ntfy). In the app, add
a server using `http://100.101.102.103:8080`, sign in with the user from 6.6, and subscribe
to your topic.

Your phone must have Tailscale connected to reach the server.

---

## Done on the server

Continue with
[pointing LACC at the server](setting-up-the-server-machine.md#part-2---point-lacc-at-the-server),
which you do on your laptop.

Keep these three things at hand:

- the Tailscale address, e.g. `100.101.102.103`
- the ntfy topic, e.g. `lacc-tesis-7h3k9x`
- the ntfy token, starting with `tk_`
