# A run, end to end

What happens between typing

    .\run.ps1 run lacc run extract_claims paper.md -c configs/denso.yaml

and reading a checked answer, function by function. Every name here is a real one, read on
27-sep; the file is in brackets. Where a step writes to the audit trail, the event it writes is
in `monospace` at the end of the line.

## 1. Before anything is sent: the command (`cli.py`, `run`)

1. **Which skill.** `_resolve_skill` finds `extract_claims` among the built-in skills, or in a
   `skills/` folder beside the configuration, where a skill written in YAML may only read
   (`core/declared.py`, ADR-048).
2. **Which configuration and which workspace.** `_load` validates the YAML into a frozen
   `Config` (`core/config.py`) and opens the `Workspace` it names (`core/workspace.py`), which
   refuses a git working tree unless the configuration says so with `workspace_in_repository`,
   and warns when it looks like a synchronised folder.
3. **Which engine.** `_build_provider` builds the Ollama provider for the model the
   configuration names, per skill if it names one (`adapters/ollama.py`, ADR-051). Nothing is
   contacted yet.
4. **The plan - pure.** `skill.plan` turns `paper.md` into an `IntendedAction` and a prompt
   template. It reads nothing and writes nothing: a plan is a description (`core/skill.py`).
5. **The preview.** `grant_for` gives the skill exactly the capabilities it declares, with the
   configuration as a ceiling that can only remove (`core/permissions.py`); `preview_action`
   says what would be read, what would be written, where the text would go, and whether all
   of it is allowed (`core/preview.py`). It is printed, with the model and what it will cost.
6. **You.** `Proceed?` - and the default is no. Declining here ends everything; nothing has
   been read and nothing is recorded.

## 2. The cycle (`cycle.py`, `run_skill` then `run_action`)

`run_skill` chooses between reading the document whole (`run_action`) and reading it in passes
of a few pages (`run_in_passes`, ADR-045). Whole:

1. **Authorise** (`_authorize`), the opening every run shares: `run_started`. The preview is
   taken again; if anything is not allowed, `run_refused` - with what was missing and which
   paths were out of bounds - and the run ends. Otherwise `permission_granted`.
2. **Read** (`_prepare`, `_fill_template`). Each declared file is resolved through the
   workspace boundary and read, up to `max_input_bytes`. Fence markers inside the document are
   removed before the prompt is assembled, so a document cannot close its own fence
   (`core/fence.py`, ADR-038): `fence_markers_removed`. Text shaped like an instruction is
   noticed, not blocked: `instruction_shapes_seen`. The standing context, if the skill uses
   it: `standing_context_used`. What was read, with the digest of each file: `files_read`.
3. **Measure, and refuse rather than cut** (`_ask`). The prompt's tokens are estimated:
   `prompt_measured`. If the configuration names the window and the prompt would not fit it
   with room left for the answer, nothing is sent - an engine given too much does not fail, it drops what does not fit and answers from
   the rest (`core/budget.py`): `prompt_too_large`.
4. **Send.** `provider.complete` - the one place a prompt reaches an engine. What came back is
   recorded with the digests of the prompt, the template and the answer, the tokens the engine
   counted, why it stopped, and how many characters it spent reasoning (never the reasoning):
   `provider_called`. Under `audit_level: full` the prompt and the answer themselves go in too.
5. **What the engine said about itself** (`_record_what_the_engine_reported`): it read less of
   the prompt than was sent, `prompt_was_truncated`; it counted more than estimated,
   `ceiling_underestimated`; it stopped for want of room, `answer_truncated`.
6. `run_finished`.
7. **Check every quotation** (`core/grounding.py`, `check_answer` then `without_repeats`). Each
   quotation the model gave is looked for in the document it names - verified, found but on
   another page, or not in the document at all: `quotations_checked` (ADR-026).
8. **Keep it, if it produces something.** For a skill that writes, the diff is shown and the
   result goes beside the original, never over it (`_offer_the_answer`, `write_new_file`):
   `revision_written` or `revision_declined` (ADR-025, ADR-039).

Every event is appended to `audit.jsonl`, chained to the one before it, and the anchor beside
it is updated (`system/audit.py`) - reading the head and appending in one turn that every
writer takes, so the window and a terminal writing at once still leave one chain (ADR-109).

## 3. After: what you are told (`cli.py`)

- `_announce` sends a notice, if a notifier is configured, carrying the trail's length and the
  start of its head digest - the one copy of the chain's state that leaves the machine
  (`adapters/ntfy.py`, ADR-049). A notifier that fails never fails a run (ADR-027).
- `_report` shows the answer; `_say_how_it_was_read` says when it was read in passes;
  `_warn_about_the_document` says what the fence removed and what read like an instruction;
  `_show_checked_quotations` shows each quotation with its verdict; `_warn_about_the_answer`
  says when the engine truncated something.

## The same shape everywhere else

A conversion (`lacc ingest`, `run_conversion`) opens with the same `_authorize` and records
`document_converted`. A question to a corpus (`lacc ask`, and the window's Ask) records
`passages_selected` - how many passages were considered and how many set aside - and goes on
through the same measuring, sending and checking (`ask_once`, `answer_prepared`). Every one
of them can be read back afterwards, record by record, in the window's Audit section
(ADR-104).
