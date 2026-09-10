# Guide - Choosing hardware for local models

What actually makes a machine good at running a language model, which is not what the
spec sheet leads with. Read this before buying anything; the answer surprises most
people and the mistake is expensive.

To set up a machine you already have, go to
[setting up the server machine](setting-up-the-server-machine.md).
## Be clear about what this buys

The obvious reason is speed. That is usually not the reason, and being wrong about it
leads to buying the wrong machine.

**What a dedicated box actually gives you is free memory.** The laptop this was developed
on reports 15.6 GB total and **2.4 GB free**, because a browser, an editor and everything
else are open. A headless machine with the same 16 GB has nearly all of it free. That is
the difference between running a 3B model and a 14B one, which is a real jump in quality
for the job LACC does.

**The second thing it gives you is being always on.** A run that takes half an hour is
fine when it happens on a machine you are not using, and tells you when it is done.

**What it does not automatically give you is speed.** Inference without a GPU is bound by
CPU and memory bandwidth. A low-power four-core mini PC will be *slower per token* than a
modern eight-core laptop, even while being *more capable* because it has the memory free
to hold a bigger model. Both things are true at once, and only measuring tells you where
the balance lands for your machine.

If you want inference that is actually fast, the thing that unlocks it is VRAM - a GPU
with enough memory to hold the model - not more CPU cores.

## What to look for if you are buying one

Generating a token means reading the whole model out of memory, once, per token. So
without a GPU the speed is set by **memory bandwidth**, not by the processor. Cores matter
for chewing through the prompt, which happens once; bandwidth matters for every token of
the answer.

That reorders the spec sheet, and puts the usual headline number near the bottom.

**1. Two memory sticks, not one.** This is the trap, because it is invisible on the
listing. A machine sold as "16 GB" may ship a single SODIMM, which runs in single channel
at **half the bandwidth** of the same 16 GB as two 8 GB sticks. Nothing in the description
distinguishes them. Look for "2x8GB" or "dual channel", or plan to buy the second stick.

Roughly, for a 14B model at Q4 weighing about 9 GB:

| Memory | Bandwidth | Tokens per second, roughly |
|---|---|---|
| DDR4-3200, single channel | 25.6 GB/s | 1-2 |
| DDR4-3200, dual channel | 51.2 GB/s | 3-4 |
| DDR5-5600, dual channel | 89.6 GB/s | 5-7 |

Those are estimates from bandwidth divided by model size, discounted for real-world
efficiency. Treat them as the shape of the difference rather than a promise.

**2. 32 GB rather than 16 GB.** Capacity decides which models are possible at all, and it
is the cheapest upgrade on the list. 32 GB puts a 14B model at a comfortable window well
within reach, and leaves the door open to a 32B one.

**3. DDR5 over DDR4** if the budget stretches, for the bandwidth row above.

**4. Six to eight cores is plenty.** Past that you are bandwidth-bound and paying for
cores that wait. This is why a Ryzen 3 4300U - four cores, DDR4, often single channel -
is a weak choice for this even though it is a perfectly good small computer.

A concrete way to read the market: a **Ryzen 7 5825U** class machine with 2x16 GB DDR4 is
the value option, and a **Ryzen 7 7735HS or 7840HS** class machine with 2x16 GB DDR5 is
roughly twice the memory bandwidth for a moderate premium. Avoid the very cheap Intel
N100 tier for this particular job: it is memory-starved in exactly the way that hurts.

One honest outlier: Apple Silicon uses unified memory with far more bandwidth than any
x86 mini PC in the same price range - a base M4 Mac mini is around 120 GB/s - and Ollama
uses its GPU. If you are not committed to Linux, it will produce more tokens per second
per unit of money than anything above. Tailscale and ntfy both run on macOS.

## If you can build a desktop instead

Everything above is about making the best of no GPU. If a tower is an option, stop
optimising CPU and buy VRAM. It is not a better version of the same choice - it is a
different order of magnitude.

The reason is the same bandwidth argument, one league up. Taking a 7-8B model, which is
the largest that fits every card below:

| Where the model sits | Bandwidth | 7-8B at Q4, roughly |
|---|---|---|
| System RAM, DDR4 dual channel | ~51 GB/s | 5-7 tokens/s |
| System RAM, DDR5 dual channel | ~90 GB/s | 10-12 tokens/s |
| RTX 4060 8 GB | ~272 GB/s | 40+ tokens/s |
| RTX 3060 12 GB | ~360 GB/s | 50+ tokens/s |
| RTX 3090 24 GB | ~936 GB/s | 100+ tokens/s |

A run that took half an hour takes a few minutes. That changes how the tool is used, not
just how fast it is - a model you can iterate against is a different tool from one you
submit a job to.

Past a certain point the number stops mattering. Once answers arrive faster than you read
them, more bandwidth buys nothing and the remaining question is only which models fit.

**VRAM capacity is a cliff, not a slope.** If the model does not fit entirely in VRAM, the
remainder spills to system memory and the speed collapses back toward the CPU numbers -
and to *worse* than pure CPU in some cases, because now it waits on both. So capacity
comes before speed when choosing a card.

**Count the context window, not just the weights.** This is the part that catches people,
and it caught the first draft of this guide. The KV cache lives in VRAM too, and it grows
with the window LACC is configured for. Its size is
`2 x layers x kv_heads x head_dim x bytes` per token - the same formula `lacc profile`
uses - and at 32,768 tokens it is not a rounding error:

| Model at Q4 | Weights | Cache at 32k, 8-bit | **Total VRAM** |
|---|---|---|---|
| 3B | 1.8 GB | 0.6 GB | 2.4 GB |
| 7-8B | 4.7 GB | 0.9 GB | **5.6 GB** |
| 14B | 9.0 GB | 3.0 GB | **12.0 GB** |
| 32B | 19.0 GB | 4.0 GB | **23.0 GB** |

At 16-bit the cache doubles: a 14B model at a 32k window wants 15 GB rather than 12. Ollama
can hold it at 8 bits with `OLLAMA_KV_CACHE_TYPE=q8_0` and flash attention enabled, and
that is worth doing - it is the difference between fitting a card and not.

Read that table against the card you are considering, remembering that a card's usable
VRAM is a few per cent below its advertised size:

| Card | VRAM | Bandwidth | What it runs at a 32k window |
|---|---|---|---|
| RTX 4060 | 8 GB | 272 GB/s | 7-8B |
| RTX 3060 | 12 GB | 360 GB/s | 7-8B, or 14B at a 16k window |
| RTX 4060 Ti | 16 GB | 288 GB/s | **14B** |
| RTX 3090 | 24 GB | 936 GB/s | 14B with room; 32B at a reduced window |

The row that surprises people is the second one. **12 GB does not buy a 14B model at the
window LACC needs for a full paper** - 12.0 GB does not fit in 11.5 usable. It buys a
choice instead: the same 7-8B model with headroom, or a 14B model over a shorter document.
Because `context_tokens` is a configuration field, that trade is yours to make explicitly
rather than something the engine decides quietly.

Three configurations worth naming:

- **The honest entry.** An **RTX 4060 8 GB**, or a used **RTX 3060 12 GB**. Both run a
  7-8B model at a full 32k window, which is already a large jump from 3B and fast enough
  that runs finish while you wait. The 3060 has more bandwidth and the 12 GB option; the
  4060 draws less power. Neither reaches 14B at a full window.
- **The one that matches the job.** An **RTX 4060 Ti 16 GB**. Unremarkable for gaming and
  frequently dismissed for it, but 16 GB is the first size that holds a 14B model *and*
  a 32k window, which is exactly what extracting claims from a whole paper asks for.
- **The do-it-properly build.** A used **RTX 3090 24 GB**, 32 to 64 GB of system RAM and
  a 750 W supply. Triple the bandwidth of the 4060 Ti and room for a 32B model at a
  reduced window. It draws a lot of power and runs hot; check the case and the supply
  before committing.

The rest of the machine barely matters. The processor loads the model and feeds the card;
a mid-range six-core part is not the bottleneck. Do not spend on the CPU what could have
been VRAM.

Once you have the machine, [setting up the server machine](setting-up-the-server-machine.md)
takes it from bare install to answering LACC.

## Measuring whether it was worth it

Do not take this guide's word for any of it, or a benchmark's. LACC can measure the thing
that actually matters to you.

`extract_claims` checks every quotation against the source and reports how many held. So
run one of your own papers through it with a small model, then with the larger one the new
hardware allows, and compare how many quotations came back **verified** rather than **not
found**. Time both runs while you are there.

A model that fabricates fewer quotations is better at this job for a reason you can point
at, measured on your sources rather than somebody else's benchmark. If the bigger model
verifies twice as many claims and takes six times as long, that is a trade you can now make
deliberately instead of by feel.
