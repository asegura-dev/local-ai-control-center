# Guide - Running the server day to day, and getting your VRAM back

If the machine running the model is also the machine you play games on, edit video on, or
otherwise want your graphics card for, you do not want a model sitting in VRAM all day.

The good news is that the thing to stop is almost never the engine. Every figure here was
measured on a real setup rather than assumed.

## The engine is not what holds your VRAM. The model is.

With no model loaded, the Ollama server process holds essentially no graphics memory. It
listens on a port and waits. Loading a model is what fills the card:

```
qwen2.5:14b     13.63 GB in VRAM     expires: 15:54:22
```

That is a 14B model on a 16 GB card, measured. And the useful part is the second column:
**it unloads itself.** Ollama keeps a model loaded for five minutes after the last request
and then releases the memory without being asked.

So for most days there is nothing to do. Finish a run, walk away, and the card is yours
again five minutes later.

### Seeing what is loaded

From your laptop, over the tailnet:

```bash
curl http://100.101.102.103:11434/api/ps
```

An empty `models` list means the card is free.

### Getting it back now

When five minutes is five minutes too long:

```bash
curl -X POST http://100.101.102.103:11434/api/generate \
  -d '{"model":"qwen2.5:14b","keep_alive":0}'
```

It answers `"done_reason":"unload"` and the memory is released immediately. This runs from
**your laptop** - there is no need to touch the server, sit at it, or connect to it any
other way.

On the server itself, the same thing is `ollama stop qwen2.5:14b`.

## Changing how long a model stays loaded

Five minutes is the default. If you alternate between LACC and something else that wants
the card, shorten it; if you run many documents in a row, lengthen it so the model is not
reloaded between them.

Per request, `keep_alive` accepts a duration: `"keep_alive": "30s"`, `"1h"`, or `0` to
unload straight after answering.

For every request, set `OLLAMA_KEEP_ALIVE` on the server - a duration like `30s`, or `0` to
never keep a model loaded at all. Reloading a 14B model costs a few seconds, so `0` trades
a little time on every run for a card that is never occupied between them.

## When you do want the engine stopped

Unloading the model is enough to free the card. Stopping the engine as well is for when you
want the port closed and nothing listening - before lending the machine to somebody, for
instance.

### Stopping it on Windows

```powershell
Get-Process -Name "ollama*" | Stop-Process -Force
```

That ends both the server and the tray application.

### Stopping it on Linux

```bash
sudo systemctl stop ollama
```

Add `sudo systemctl disable ollama` if you do not want it starting at boot.

## Starting it again

### On Windows, and the trap that comes with it

Starting Ollama is easy; starting it *so that it is actually reachable* has one failure
that costs an afternoon, because it announces itself as silence.

If `OLLAMA_HOST` names your Tailscale address, Ollama can only bind to it once Tailscale
has brought the interface up. At login it usually loses that race: the bind fails, **the
process stays running**, nothing is listening, and no error appears anywhere. From your
laptop it looks exactly like a firewall problem.

The symptom is unmistakable once you know it. On the server:

```powershell
Get-NetTCPConnection -LocalPort 11434 -State Listen
```

Processes running, nothing listening - that is this, every time.

Starting it by hand, after Tailscale is up, always works:

```powershell
$env:OLLAMA_HOST = "100.101.102.103:11434"
ollama serve
```

That holds the terminal open, which is fine for an afternoon and wrong for a server. For
something durable, either:

- **A scheduled task at logon with a delay.** In Task Scheduler, create a task that runs
  `ollama serve` at logon, delayed by one minute, and disable Ollama's own autostart so the
  two do not fight. Blunt, and it works.
- **Or remove the race entirely with Tailscale Serve**, below.

### On Linux

```bash
sudo systemctl start ollama
```

systemd holds the environment from the unit file, so there is no login session to inherit
from and no race of the kind Windows has. If the interface is not up in time, add
`After=tailscaled.service` to the unit.

## The arrangement that avoids all of this

The race exists because Ollama is told to bind to an address that does not exist yet.
Tailscale Serve removes that: Ollama binds to `127.0.0.1`, which always exists, and
Tailscale forwards tailnet traffic to it.

```
tailscale serve --help     # check the exact syntax for your version first
```

The syntax has changed across Tailscale releases, so read the help rather than pasting from
here. The shape is a TCP proxy from port 11434 on the tailnet to `127.0.0.1:11434`.

It is worth the ten minutes for a reason beyond convenience. With this arrangement Ollama
is **not listening on any network interface at all** - not your home network, not a café
Wi-Fi, not a misconfigured firewall's idea of your network. The tailnet is the only path in,
and Tailscale authenticates it. Binding to the tailnet address directly leaves you relying
on a firewall rule still being correct in six months.

Remember to remove `OLLAMA_HOST` if you switch, so Ollama goes back to its localhost
default:

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_HOST", $null, "Machine")
```

## A note on the context window and your card

A model's weights are not all it occupies. The context window LACC asks for is held in
VRAM too, and it is not small: a 14B model at Q4 is about 9 GB of weights, and a 32,768
token window adds roughly 6 GB more at 16-bit - which is why the measurement at the top of
this page reads 13.63 GB rather than 9.

Holding that cache at 8 bits roughly halves it, at no cost worth noticing:

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_FLASH_ATTENTION", "1", "Machine")
[Environment]::SetEnvironmentVariable("OLLAMA_KV_CACHE_TYPE", "q8_0", "Machine")
```

On a 16 GB card that is the difference between a 14B model at a full window fitting
comfortably and fitting by a hair. See
[choosing hardware](choosing-hardware-for-local-models.md#if-you-can-build-a-desktop-instead)
for the sizing table.
