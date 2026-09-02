# ADR-014 - Reading file contents: exercising the read_files permission

- **Status:** Accepted - implemented (v0.13.0)
- **Date:** 2026-07-26
- **Context:** The `summarize_file` skill declares `read_files` and the permission is
  granted, but nothing reads the file: the skill's prompt names the path without its
  contents, so a real model answers that it lacks the content. The permission exists
  and is checked; it is simply never exercised. This ADR makes the cycle read the
  declared files, after the permission is confirmed, and feed their contents into the
  prompt - turning a granted-but-unused permission into a real read.

## Decision

### 1. The cycle reads, not the skill's plan

Reading a file is a side effect, and the skill's `plan` is pure by design (ADR-009):
it describes intent and touches nothing. So the cycle performs the read, not the plan.
The skill declares which files it needs through the action's `targets`, as it already
does; the cycle reads those targets when the time comes.

### 2. Reading happens after confirmation, before the provider

The cycle's order is preview, confirm, execute, record (ADR-008). The read is a side
effect, so it belongs after the human confirms - never read a file for an action the
user declines. It also must precede the provider call, since the contents feed the
prompt. The read is therefore inserted between confirmation and the provider call.

### 3. The permission and the boundary are already enforced

No new permission is added. `read_files` already exists and is already granted or
withheld by the existing system; the preview already checks that targets sit inside
the workspace. By the time the cycle reads, the preview has confirmed both. The read
trusts what the preview already verified, rather than re-checking.

### 4. The skill supplies a template; the cycle fills it

The skill's `plan` produces a prompt *template* with a placeholder for file content,
kept separate from the final prompt. The cycle reads the targets and produces the
final prompt by filling the template. Separating template from result keeps the plan
pure (it never holds file content) and keeps the filling - a side effect's product -
in the cycle. Configurable prompt templates (external, user-edited) are a later
phase; this ADR only splits template from filled prompt.

### 5. A read failure fails clearly, like any external failure

If a target cannot be read (missing, unreadable), the cycle does not crash: it records
the failure and returns a clear message, the same posture used for provider failures.
A file that passed the boundary check can still fail to read at the moment of reading,
so the read is attempted and its failure translated.

### 6. File contents follow the audit privacy rule

File content is user content, as sensitive as a prompt. It follows the same rule as
prompts and completions (ADR-006): recorded under `audit_level: full`, omitted under
`standard`. Reading a file must not leak its contents into a standard-level trail.

## Trade-off

Putting the read in the cycle rather than the skill means the cycle grows knowledge of
file reading, not just orchestration. Accepted: the cycle is already where side effects
and permission enforcement live, and keeping the read there preserves the skill's plan
as pure description. A skill that reads in its plan would break the purity that makes
plans safe to preview.

Splitting template from filled prompt adds a field to the plan rather than reusing the
single prompt string with a marker. The extra field is accepted because reusing one
field for both the unfilled template and the filled result blurs what the plan holds;
a pure plan should never contain file content, and a separate template field makes that
impossible by construction.

Not building configurable prompt templates now leaves prompt wording in code. Accepted:
external templates are a real feature with their own questions (where the file lives,
how variables are validated) and do not belong bolted onto the read. Reading a file is
the smaller, load-bearing step; configurability builds on top later.

## Consequences

- `summarize_file` produces a real summary: the file's contents reach the model.
- The cycle reads declared targets after confirmation, under the already-enforced
  `read_files` permission and workspace boundary.
- `SkillPlan` gains a prompt template separate from the final prompt the cycle builds.
- Read failures are reported clearly, not raised as raw errors.
- File contents are audited only under `full`, never `standard`.
- This is the first step toward working with documents (summaries now; multiple files
  and dialogue later). Chapter 1 and the CHANGELOG are updated in this phase.