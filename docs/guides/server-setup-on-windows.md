# Guide - Setting up the server machine, on Windows

Follow these steps in order on the machine that will run the model. Written for Windows 10
and 11.

If your server runs Linux, use [the Linux guide](server-setup-on-linux.md) instead. For
what you are building and why, see
[setting up the server machine](setting-up-the-server-machine.md).

Several steps need **PowerShell as Administrator**: press `Win`, type `PowerShell`, then
right-click *Windows PowerShell* and choose *Run as administrator*. Where a step says
"as Administrator", it means that window.

Set aside about an hour. Most of it is downloading.

---

## Step 1 - Join the machine to your private network

[Tailscale](https://tailscale.com) gives every device you enrol a private address that only
your own devices can reach. No ports are opened on your router, and nothing here is exposed
to the internet.

**1.1** Create a free account at [login.tailscale.com](https://login.tailscale.com/start).

**1.2** Download the Windows installer from
[tailscale.com/download/windows](https://tailscale.com/download/windows) and run it.

**1.3** After installing, Tailscale appears in the system tray, near the clock. Click it and
sign in. The machine joins your network.

**1.4** Find the address it was given. In PowerShell:

```powershell
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

```
ping 100.101.102.103
```

You should get replies. **If you do not, stop here.** Nothing after this point can work,
and every later problem will look like a different problem. Check that Tailscale shows as
connected on both devices.

---

## Step 2 - Install the engine

[Ollama](https://ollama.com) is what actually runs the model.

**2.1** Download the installer from [ollama.com/download/windows](https://ollama.com/download/windows)
and run it. It installs and starts automatically, appearing in the system tray.

**2.2** Confirm it responds. In PowerShell:

```powershell
ollama --version
```

---

## Step 3 - Restrict the engine to your private network

**Do not skip this step.** Ollama has no accounts, no passwords and no tokens of any kind.
Anyone who can reach its port can use it and read what you send it, and the prompts LACC
sends contain the text of your documents.

Most instructions on the internet say to set `OLLAMA_HOST=0.0.0.0`. That makes it listen on
**every** network the machine is connected to - your home network, your office network, any
Wi-Fi it joins in future. Bind it to the Tailscale address instead, so only your own
devices can reach it.

**3.1** In PowerShell **as Administrator**, using **your** address:

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_HOST", "100.101.102.103:11434", "Machine")
```

There is no output. That is normal.

**3.2** **Sign out of Windows and back in.** This is a required step, not a fallback, and
skipping it is the single most common reason this guide appears not to work.

A process inherits its environment from whatever started it. Ollama's tray application was
started by your desktop session, which was itself started before the variable existed - so
quitting Ollama from the tray and starting it again hands it the *same old environment*,
with no `OLLAMA_HOST` in it. Nothing reports an error. It simply keeps listening on
localhost as though you had changed nothing.

Signing out and back in rebuilds the session with the new variable. A full restart also
works.

If Ollama runs as a Windows service on your installation, restarting the service is enough:

```powershell
Get-Service -Name "Ollama*"          # if this finds one:
Restart-Service -Name "Ollama"
```

### Checkpoint - verify, do not assume

This check matters more than the setting, because a typo leaves it listening everywhere and
nothing warns you.

```powershell
Get-NetTCPConnection -LocalPort 11434 -State Listen | Select-Object LocalAddress, LocalPort
```

You should see **your Tailscale address**:

```
LocalAddress     LocalPort
------------     ---------
100.101.102.103      11434
```

What you see tells you which thing went wrong:

| It shows               | What happened                                                               |
| ---------------------- | --------------------------------------------------------------------------- |
| your Tailscale address | Correct. Continue to step 4.                                                |
| `127.0.0.1`            | The variable did not reach Ollama. Almost always 3.2: sign out and back in. |
| `0.0.0.0` or `::`      | It is listening on **every** network. Check 3.1 for a typo and repeat.      |

If it still shows `127.0.0.1` after signing out, confirm the variable actually exists:

```powershell
[Environment]::GetEnvironmentVariable("OLLAMA_HOST", "Machine")
```

Nothing printed means 3.1 did not take - it needs an Administrator PowerShell, and it fails
silently without one.

---

## Step 4 - Let it through the firewall

**This step is required, and skipping it produces the most confusing symptom in the guide.**

Windows Defender Firewall blocks unsolicited inbound connections, and it *drops* them
rather than refusing them. So a client does not get "connection refused" - it gets nothing,
and waits until it times out. Everything looks correctly configured, the engine is running,
the address is right, and the connection simply hangs.

The Ollama installer creates no rule, because by default Ollama listens only on localhost
and does not need one. Binding it to the Tailscale address in step 3 is what makes the rule
necessary.

In PowerShell **as Administrator**, using your own address is not needed here - this
restricts the rule by *source*, to Tailscale's address range:

```powershell
New-NetFirewallRule -DisplayName "Ollama on Tailscale" -Direction Inbound `
  -LocalPort 11434 -Protocol TCP -Action Allow -RemoteAddress 100.64.0.0/10
```

`-RemoteAddress 100.64.0.0/10` is the part that matters. Tailscale hands out addresses from
that range, so the rule accepts connections from your own devices and from nothing else. A
blanket rule without it would open the port to every network the machine joins, which is
the thing step 3 was for.

Confirm it exists:

```powershell
Get-NetFirewallRule -DisplayName "Ollama on Tailscale" | Select-Object DisplayName, Enabled
```

Then, from your **laptop**, check that the engine now answers:

```
curl http://100.101.102.103:11434/api/tags
```

A block of JSON means step 3 and step 4 are both done. A timeout means the rule is missing
or the bind address is wrong; "connection refused" means Ollama is not running.

> **If you installed ntfy under Docker later on, it needs no equivalent step.** Docker
> Desktop adds its own firewall rules when it publishes a port, which is why ntfy can work
> while Ollama does not - a difference that makes the engine look broken when the firewall
> is the only thing between them.

## Step 5 - Download a model

```powershell
ollama pull qwen2.5:7b
```

This downloads several gigabytes.

`qwen2.5:7b` is a safe starting point: it fits almost any machine and is a large step up
from a 3B model. If your server has plenty of memory, or an NVIDIA graphics card, the
[sizing tables](choosing-hardware-for-local-models.md#if-you-can-build-a-desktop-instead) say
what else will fit - remembering that the context window takes memory too, which is the
part people forget.

**5.1** If the machine has an NVIDIA card, confirm the model is actually using it. In one
PowerShell window:

```powershell
ollama run qwen2.5:7b "hello"
```

and while it answers, in a second window:

```powershell
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

ntfy has no native Windows installer. The practical way to run it is Docker.

**6.1** Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and let it
finish its first-run setup. It will ask to enable WSL 2 and may require a restart.

**6.2** Create a configuration file at `C:\ntfy\server.yml`. In PowerShell:

```powershell
New-Item -ItemType Directory -Force C:\ntfy | Out-Null
@'
listen-http: ":80"
base-url: "http://100.101.102.103:8080"
auth-file: "/var/lib/ntfy/user.db"
auth-default-access: "deny-all"
'@ | Set-Content -Encoding utf8 C:\ntfy\server.yml
```

Replace the address in `base-url` with yours. `listen-http: ":80"` is correct as written -
that is the port *inside* the container, and step 6.3 maps it to your Tailscale address.

`auth-default-access: "deny-all"` is the important line. Without it, anybody who can reach
the server can read and send notifications on any topic.

**6.3** Start the container, using **your** address:

```powershell
docker run -d --name ntfy --restart unless-stopped `
  -p 100.101.102.103:8080:80 `
  -v C:\ntfy\server.yml:/etc/ntfy/server.yml `
  -v ntfy-data:/var/lib/ntfy `
  binwiederhier/ntfy serve
```

Writing `-p 100.101.102.103:8080:80` rather than `-p 8080:80` is what keeps it off your
other networks. The same reasoning as Ollama in step 3.

**6.4** Confirm it is running:

```powershell
docker ps
```

You should see `ntfy` with a status starting `Up`.

**6.5** Create a user. It will ask for a password:

```powershell
docker exec -it ntfy ntfy user add --role=admin lacc
```

**6.6** Issue a token:

```powershell
docker exec -it ntfy ntfy token add lacc
```

It prints something starting with `tk_`. **Copy it now** - it is shown once. It goes into
an environment variable later, never into a file.

**6.7** Choose a topic name. A topic is just a label that groups notifications, but treat it
as a secret: pick something nobody would guess.

```
lacc-tesis-7h3k9x
```

Not `lacc`. Write it down next to the token.

**6.8** On your phone, install the ntfy app from the
[App Store](https://apps.apple.com/app/ntfy/id1625396347) or
[Google Play](https://play.google.com/store/apps/details?id=io.heckel.ntfy). In the app, add
a server using `http://100.101.102.103:8080`, sign in with the user from 6.5, and subscribe
to your topic.

Your phone must have Tailscale connected to reach the server.

---

## One thing to watch on Windows

A Windows machine that goes to sleep stops answering. If the server is meant to be
available while you work elsewhere, set *Power & sleep* to never sleep, and consider
disabling *Fast Startup*, which can leave services in an odd state after a shutdown.

---

## Done on the server

Continue with
[pointing LACC at the server](setting-up-the-server-machine.md#part-2---point-lacc-at-the-server),
which you do on your laptop.

Keep these three things at hand:

- the Tailscale address, e.g. `100.101.102.103`
- the ntfy topic, e.g. `lacc-tesis-7h3k9x`
- the ntfy token, starting with `tk_`
