"""Command-line interface: the `lacc` command.

The first human interface to the system (ADR-010). Built with Typer and rendered
with Rich, both confined here so the core stays free of interface code. `run` plans
a skill, previews it, asks for confirmation (defaulting to no), and executes;
`preview` shows what would happen without doing it.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from local_ai_control_center.adapters.asking import AskingJudge
from local_ai_control_center.adapters.crossref import CrossrefRegistry, RememberedRegistry
from local_ai_control_center.adapters.dense import DenseRetriever, FusedRetriever
from local_ai_control_center.adapters.documents import (
    HiddenText,
    converter_for,
    embedded_metadata,
    embedded_outline,
)
from local_ai_control_center.adapters.embedding import OllamaEmbedder
from local_ai_control_center.adapters.mock import MockProvider
from local_ai_control_center.adapters.ntfy import notifier_from_config
from local_ai_control_center.adapters.ollama import (
    OllamaProvider,
    check_engine,
    resolve_engine_host,
)
from local_ai_control_center.adapters.vectors import SUFFIX as VECTOR_SUFFIX
from local_ai_control_center.adapters.words import WordRetriever
from local_ai_control_center.core.budget import (
    CHARS_PER_TOKEN,
    answer_reserve,
    estimate_tokens,
)
from local_ai_control_center.core.config import DOTENV_FILENAME, Config, load_config, load_dotenv
from local_ai_control_center.core.corpus import CollectedClaim, about, parse_corpus
from local_ai_control_center.core.declared import (
    DeclarationError,
    FileSkill,
    load_declared_skills,
)
from local_ai_control_center.core.grounding import (
    CheckedClaim,
    check_answer,
    without_repeats,
)
from local_ai_control_center.core.headings import headings_in, matching
from local_ai_control_center.core.passes import PageRangeError
from local_ai_control_center.core.permissions import grant
from local_ai_control_center.core.preview import ExecutionPreview, IntendedAction, preview_action
from local_ai_control_center.core.references import (
    as_one_line,
    references_in,
    shortened,
    without_truncations,
)
from local_ai_control_center.core.run import Progress, ProgressFn, new_run_id
from local_ai_control_center.core.sections import section_of, sections_in
from local_ai_control_center.core.skill import (
    AskCorpusSkill,
    AssessSourceSkill,
    CritiqueFileSkill,
    ExtractClaimsSkill,
    ReviseFileSkill,
    Skill,
    SkillPlan,
    SummarizeFileSkill,
    grant_for,
)
from local_ai_control_center.core.workspace import (
    Workspace,
    WorkspaceExposed,
    sync_folder_suspicion,
    workspace_from_config,
)
from local_ai_control_center.cycle import (
    WINDOW_TOLERANCE,
    CannotReadInPasses,
    PromptTooLargeError,
    ReadError,
    RunResult,
    answer_prepared,
    ask_once,
    run_conversion,
    run_skill,
    write_new_file,
)
from local_ai_control_center.features.appearance import (
    WINDOW_PREFERENCES,
    preferences_from,
)
from local_ai_control_center.features.ask import (
    Asked,
    Prepared,
    might_support,
    prepare,
)
from local_ai_control_center.features.bibliography import as_entry, bibliography
from local_ai_control_center.features.commands import commands_of
from local_ai_control_center.features.corpus import (
    assembled,
    collected_markdown,
    recheck,
)
from local_ai_control_center.features.coverage import (
    CONTROL_MARK,
    REACHES_SUFFIX,
    Measured,
    missing_control,
    reach_of,
    topics_in,
)
from local_ai_control_center.features.coverage import (
    report as coverage_report,
)
from local_ai_control_center.features.identity import (
    establish,
    established_for,
    opening_of,
    printed_dois,
)
from local_ai_control_center.features.measure import spread
from local_ai_control_center.features.navigate import ranked
from local_ai_control_center.features.prompts import prompts_of
from local_ai_control_center.features.review import (
    FINDINGS_SUFFIX,
    Finding,
    Reviewed,
    concluded,
    paragraphs_in,
    report,
)
from local_ai_control_center.features.stages import TAKEN_FROM, stages_in
from local_ai_control_center.features.status import EngineSeen, status_of
from local_ai_control_center.ports.converter import ConversionError, Converter
from local_ai_control_center.ports.embedder import EmbeddingError
from local_ai_control_center.ports.notifier import Notification, NotifierMisconfigured
from local_ai_control_center.ports.provider import Provider, ProviderError
from local_ai_control_center.ports.registry import RegistryError, Work
from local_ai_control_center.ports.retriever import Passage, Retriever
from local_ai_control_center.system.audit import (
    AnchorCheck,
    AuditLog,
    check_anchor,
    digest_of,
    verify_chain,
)
from local_ai_control_center.system.profiler import SystemProfile, profile_system

DEFAULT_CONFIG_PATH = Path("configs/config.yaml")

"""Where LACC looks when no --config is given.

A folder rather than a single file, because more than one is normal: an engine on
this machine and an engine elsewhere are different configurations of the same tool.
The whole folder is ignored by git, so a private one cannot be committed by accident.
Only this exact path is a default - LACC never searches for a configuration, since
guessing which one was meant is precisely what a tool that sends documents somewhere
must not do.
"""

_SKILLS: dict[str, Skill] = {
    "summarize_file": SummarizeFileSkill(),
    "critique_file": CritiqueFileSkill(),
    "revise_file": ReviseFileSkill(),
    "extract_claims": ExtractClaimsSkill(),
    "assess_source": AssessSourceSkill(),
}

app = typer.Typer(
    help="Local AI Control Center - run AI-assisted skills with control and audit.",
    no_args_is_help=True,
)


def _console() -> Console:
    """A console that can print what a paper contains.

    A Windows terminal defaults to a legacy code page - cp1252 here - and Rich writes
    through it, so a single character outside it raises `UnicodeEncodeError` **while
    printing**. That is not cosmetic: it happened after a sixty-second answer had already
    been produced, and it ended the run before the quotations were checked. The character
    was a greater-or-equal sign, in a corpus of medical papers (ADR-062).

    The stream is put into UTF-8 and told to replace what it still cannot encode. Replacing
    is right here and would be wrong almost anywhere else in this project: this is the last
    step before a person's eyes, the answer itself is already recorded, and a question mark
    where a sign should be is a better outcome than no answer at all.
    """
    for stream in (sys.stdout, sys.stderr):
        # A stream that cannot be reconfigured - a pipe, a capture, a test harness - is
        # left as it was. `_show` below is what keeps a failure from ending a run.
        with contextlib.suppress(AttributeError, OSError, ValueError):
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    return Console()


console = _console()


def _show(text: str) -> None:
    """Print an answer the engine produced, and never let printing lose it.

    Everything after this call is the part that matters - the quotations are checked, the
    readings are judged, the discards are reported - and all of it was lost to an exception
    raised while writing to a terminal. A display is the one place in this program where
    failing quietly is better than failing correctly (ADR-062).
    """
    try:
        console.print(text)
    except (UnicodeEncodeError, OSError):
        plain = text.encode("ascii", "replace").decode("ascii")
        try:
            console.print(plain)
            console.print(
                "[yellow]Some characters could not be shown by this terminal and were "
                "replaced. The answer itself is unchanged.[/yellow]"
            )
        except (UnicodeEncodeError, OSError):
            console.print("[yellow]The answer could not be displayed by this terminal.[/yellow]")


class ProviderChoice(StrEnum):
    """The providers the CLI can run a skill against."""

    ollama = "ollama"
    mock = "mock"


def _known_skills(config_path: Path) -> dict[str, Skill]:
    """The built-in skills, plus any declared beside the configuration (ADR-048).

    A declaration cannot replace a built-in one. The five in code had their wording measured
    and their decisions argued in records; a file that could shadow `extract_claims` would
    let somebody change what verification means by putting a file somewhere.
    """
    known: dict[str, Skill] = dict(_SKILLS)
    try:
        declared = load_declared_skills(config_path)
    except DeclarationError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error
    for skill in declared:
        if skill.name in _SKILLS:
            console.print(
                f"[red]A declared skill is named {skill.name}, which is built in.[/red] "
                "Rename it: a file must not be able to replace a skill whose behaviour was "
                "measured."
            )
            raise typer.Exit(code=1)
        known[skill.name] = skill
    return known


def _resolve_skill(name: str, config_path: Path = DEFAULT_CONFIG_PATH) -> Skill:
    """Look up a skill by name, or exit with the list of known skills."""
    known = _known_skills(config_path)
    skill = known.get(name)
    if skill is None:
        built_in = ", ".join(sorted(_SKILLS))
        declared = ", ".join(sorted(set(known) - set(_SKILLS)))
        console.print(f"[red]Unknown skill:[/red] {name}")
        console.print(f"Built in: {built_in}")
        console.print(f"Declared: {declared or '(none)'}")
        raise typer.Exit(code=1)
    if isinstance(skill, FileSkill):
        console.print(
            f"[yellow]{name} is a declared skill.[/yellow] Its wording came from a file and "
            "was not reviewed by anybody but its author. What it may do is unchanged: the "
            "same permissions, the same preview, the same checking."
        )
    return skill


def _plan_or_exit(skill: Skill, requests: tuple[str, ...], config: Config) -> SkillPlan:
    """Plan the skill, or exit clearly when it cannot take what it was given."""
    try:
        return skill.plan(requests, config)
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error


def _approve(difference: str) -> bool:
    """Show what would change and ask whether to keep it. Defaults to no.

    The second question of a revision, and the one that matters: a preview says what LACC
    intends, a diff says what it produced (ADR-025).
    """
    if not difference:
        console.print("[yellow]The revision is identical to the original.[/yellow]")
        return False
    rendered = Text()
    for line in difference.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            rendered.append(line + chr(10), style="green")
        elif line.startswith("-") and not line.startswith("---"):
            rendered.append(line + chr(10), style="red")
        elif line.startswith("@@"):
            rendered.append(line + chr(10), style="cyan")
        else:
            rendered.append(line + chr(10), style="dim")
    console.print(Panel(rendered, title="What the revision would change", expand=False))
    return typer.confirm("Keep this revision?", default=False)


def _load(config_path: Path) -> tuple[Config, Workspace]:
    """Load configuration and build the workspace, or exit on failure.

    A `.env` beside the configuration supplies the variables it names, without overwriting
    anything already in the environment (ADR-030). It is read from that one directory: LACC
    does not search, because guessing which configuration was meant is what a tool that
    sends documents somewhere must not do.
    """
    load_dotenv(config_path.parent)
    try:
        config = load_config(config_path)
    except (OSError, ValueError) as error:
        console.print(f"[red]Could not load configuration:[/red] {error}")
        raise typer.Exit(code=1) from error

    try:
        workspace = workspace_from_config(config)
    except WorkspaceExposed as error:
        console.print(f"[red]Refusing to use this workspace.[/red] {error}")
        raise typer.Exit(code=1) from error

    suspicion = sync_folder_suspicion(workspace.root)
    if suspicion is not None:
        console.print(f"[yellow]Warning.[/yellow] {suspicion}")
    return config, workspace


def _show_preview(preview: ExecutionPreview) -> None:
    """Render a preview in a panel."""
    console.print(Panel(preview.render(), title="Execution preview", expand=False))


def _say_what_it_will_cost(
    action: IntendedAction,
    config: Config,
    workspace: Workspace,
    in_passes: bool,
    pages_per_pass: int | None,
) -> None:
    """Say how many passes a run will take, before the question that starts it.

    Estimated from the file's **size**, not its contents. The discipline is preview, then
    confirm, then read; reading a document to tell someone what reading it would cost would
    invert that for the sake of a nicer number (ADR-045).

    The warning at the end is the point. A document large enough to need many passes is
    almost never one somebody needs in full - it is a guideline or a manual, and the part
    they want is a chapter. Saying so before twenty minutes of engine time is cheaper than
    saying it after.
    """
    if not (in_passes or pages_per_pass is not None) or config.context_tokens is None:
        return
    if len(action.targets) != 1:
        return
    try:
        size = workspace.resolve_within(action.targets[0]).stat().st_size
    except (OSError, ValueError):
        return

    budget = config.context_tokens - answer_reserve(config.context_tokens)
    tokens = -(-size // CHARS_PER_TOKEN)
    per_pass = budget if pages_per_pass is None else max(1, budget // 4)
    passes = max(1, -(-tokens // max(1, per_pass)))
    if passes < 2:
        return

    console.print(
        f"[yellow]About {passes} passes[/yellow] over roughly {tokens:,} tokens of document. "
        "Each pass is one call to the engine."
    )
    if passes >= _MANY_PASSES:
        console.print(
            "A document this long is rarely one you need in full - it is a guideline or a "
            "manual, and the part you are citing is a chapter. Reading only that chapter "
            "costs minutes rather than an afternoon, and every claim that comes back is "
            "about the part you will actually cite. LACC cannot yet cut one out for you."
        )


def _confirm(preview: ExecutionPreview) -> bool:
    """Ask the user whether to proceed. Defaults to no."""
    _show_preview(preview)
    return typer.confirm("Proceed?", default=False)


@app.command()
def run(
    skill: Annotated[str, typer.Argument(help="Name of the skill to run.")],
    requests: Annotated[
        list[str],
        typer.Argument(help="One or more paths inside the workspace."),
    ],
    config_path: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to the configuration file."),
    ] = DEFAULT_CONFIG_PATH,
    provider_choice: Annotated[
        ProviderChoice,
        typer.Option("--provider", help="Which provider to run against."),
    ] = ProviderChoice.ollama,
    in_passes: Annotated[
        bool,
        typer.Option(
            "--in-passes",
            help="Read a document in several passes over its pages. Needed for one too "
            "large for the window, and worth it for one that fits: measured at six "
            "times the quotations, because a prompt asks once however much it is "
            "shown (ADR-089).",
        ),
    ] = False,
    pages_per_pass: Annotated[
        int | None,
        typer.Option(
            "--pages-per-pass",
            min=1,
            help=(
                "Read in passes of this many pages, even when the document "
                "fits. Measured: about three pages gave 4.6x the verified "
                "quotations for twice the time."
            ),
        ),
    ] = None,
) -> None:
    """Plan a skill, preview it, confirm, then execute and record it."""
    resolved = _resolve_skill(skill, config_path)
    config, workspace = _load(config_path)
    audit = AuditLog(workspace, config)

    try:
        provider = _build_provider(provider_choice, config, resolved.name)
    except ProviderError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    plan = _plan_or_exit(resolved, tuple(requests), config)
    preview = preview_action(
        plan.action, grant_for(resolved, config), config, workspace, config.remote_engine
    )
    _show_preview(preview)
    _say_which_model(config, resolved.name)
    _say_what_it_will_cost(plan.action, config, workspace, in_passes, pages_per_pass)
    if not typer.confirm("Proceed?", default=False):
        console.print("[yellow]Declined.[/yellow] Nothing was run.")
        return

    run_id = new_run_id()
    generating = provider_choice is ProviderChoice.ollama
    started = time.monotonic()
    try:
        if generating:
            with console.status("Contacting Ollama...") as status:
                status.update(
                    "Reading in passes..."
                    if in_passes or pages_per_pass
                    else "Generating... (the first run loads the model into memory and may "
                    "take longer)"
                )
                result = _do_run(
                    resolved,
                    tuple(requests),
                    config,
                    workspace,
                    provider,
                    audit,
                    run_id,
                    in_passes,
                    pages_per_pass,
                    _onto(status),
                )
        else:
            result = _do_run(
                resolved,
                tuple(requests),
                config,
                workspace,
                provider,
                audit,
                run_id,
                in_passes,
                pages_per_pass,
            )
    except (ProviderError, ReadError, PromptTooLargeError, CannotReadInPasses) as error:
        _announce(resolved.name, "failed", time.monotonic() - started, config, audit, run_id)
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    _announce(resolved.name, result.outcome, time.monotonic() - started, config, audit, run_id)
    _report(result)
    _say_how_it_was_read(result)
    _warn_about_the_document(result)
    _show_checked_quotations(result)
    _warn_about_the_answer(result, config)
    if config.context_tokens is None:
        _warn_no_context_ceiling()


def _say_how_it_was_read(result: RunResult) -> None:
    """Say when the document was read in pieces, because the answer reads as if it was not.

    A model that never held the whole document cannot speak for the whole document, and a
    reader who is not told will assume it did (ADR-045).
    """
    if result.passes > 1:
        console.print(
            f"[yellow]Read in {result.passes} passes.[/yellow] The model never saw the whole "
            "document at once, so anything it says about the document as a whole rests on "
            "less than it appears to. Every quotation was still checked against all of it."
        )


def _warn_about_the_document(result: RunResult) -> None:
    """Say when the document tried to be an instruction, beside the answer it produced.

    Placed here rather than before the run because it is only knowable after reading, and
    because next to the answer is when a person is deciding whether to trust it.

    Detection, never a verdict: a model can obey something no pattern catches, so this
    reports what was seen and leaves the judgement where it belongs (ADR-038).
    """
    if result.markers_removed:
        console.print(
            f"[yellow]{result.markers_removed} fence markers were removed from the "
            "document[/yellow] before it was sent. A document carrying one could otherwise "
            "end its own fence and have the rest read as instructions."
        )
    if result.instruction_shapes:
        console.print(
            "[yellow]The document contains text shaped like an instruction:[/yellow] "
            + ", ".join(result.instruction_shapes)
            + "."
        )
        console.print(
            "[dim]LACC cannot stop a model from being influenced by what it reads. Nothing "
            "was run, opened or sent because of it - but read the answer above knowing "
            "the document was trying something.[/dim]"
        )


def _show_checked_quotations(result: RunResult) -> None:
    """Say which quotations were found in the source and which were not.

    Nothing is hidden: an unverified claim stays in the answer above and is marked here,
    because the point is to show what the model did rather than to tidy it away (ADR-026).
    """
    if not result.checked_claims:
        return

    marks = {
        "verified": "[green]found[/green]",
        "not_found": "[red]NOT IN THE DOCUMENT[/red]",
        "page_unknown": "[yellow]found, page unknown[/yellow]",
    }
    table = Table(title="Quotations checked against the source", expand=False)
    table.add_column("Claim")
    table.add_column("Quotation")
    table.add_column("Page")
    table.add_column("Checked")
    for checked in result.checked_claims:
        # The page shown is the one LACC located, never the one the model claimed: the
        # first is right by construction, and the second is a citation error waiting to
        # be repeated by whoever trusts it (ADR-031).
        page = str(checked.found_on_page) if checked.found_on_page else "-"
        table.add_row(
            checked.claim.claim[:60],
            checked.claim.quote[:40],
            page,
            marks[checked.verdict],
        )
    console.print(table)

    _offer_the_nearest_text(result)

    # Counted by whether the quotation is in the document, not by whether a page could be
    # named. Tallying an unplaceable quotation beside a fabricated one reports the tool's
    # limit as the model's dishonesty (ADR-042).
    missing = sum(1 for checked in result.checked_claims if not checked.found)
    unplaced = sum(1 for checked in result.checked_claims if checked.found and not checked.holds)
    if missing:
        console.print(
            f"[red]{missing} of {len(result.checked_claims)} quotations are not in the "
            "document.[/red] Do not cite those without opening it yourself."
        )
    if unplaced:
        console.print(
            f"[dim]{unplaced} are in the document but could not be placed on a page - the "
            "source has no page markers, or the passage runs across a break.[/dim]"
        )


def _offer_the_nearest_text(result: RunResult) -> None:
    """For a quotation that was not found, show what the document does contain.

    The failure this exists for is a real sentence with the number changed: right topic,
    right wording, false figure. Reporting only "not found" leaves someone hunting through
    a PDF for a sentence they have just been told is wrong (ADR-034).
    """
    corrections = [
        checked
        for checked in result.checked_claims
        if checked.verdict == "not_found" and checked.nearest
    ]
    if not corrections:
        return

    console.print()
    for checked in corrections:
        console.print("[red]Not in the document:[/red]")
        console.print(f"  [dim]the model wrote  [/dim] {checked.claim.quote[:150]}")
        # "Closest text", never "what it meant": this is a string match, and LACC does not
        # know what the model was reaching for.
        console.print(f"  [green]closest in source[/green] {checked.nearest[:150]}")


def _warn_about_the_answer(result: RunResult, config: Config) -> None:
    """Say when the engine's own numbers show the answer is not what it looks like.

    Both signals arrive after the answer does, so neither could have prevented it
    (ADR-020). Reporting them is the whole of what can honestly be done: an answer built
    on a document the engine truncated, and an answer that stopped for want of room, both
    read exactly like answers.
    """
    completion = result.completion
    if completion is None:
        return

    if completion.prompt_tokens is not None and config.context_tokens is not None:
        window = config.context_tokens
        if completion.prompt_tokens >= window - WINDOW_TOLERANCE:
            console.print(
                f"[red]This answer is built on part of the document.[/red] The engine "
                f"counted {completion.prompt_tokens:,} tokens, filling the {window:,}-token "
                "window, which means it dropped what did not fit and answered from the "
                "rest. Use a shorter document, or raise `context_tokens` if the machine "
                "can hold more."
            )
        elif completion.prompt_tokens > window - answer_reserve(window):
            console.print(
                f"[yellow]LACC underestimated this prompt.[/yellow] The engine counted "
                f"{completion.prompt_tokens:,} tokens, over the budget checked against, "
                "though the prompt still fitted the window. The answer stands; the "
                "arithmetic was off on this text."
            )

    if completion.finish_reason == "length":
        console.print(
            "[yellow]The answer stopped for want of room[/yellow], not because the model "
            "had finished. Raise `context_tokens` if the machine can hold more."
        )


def _warn_no_context_ceiling() -> None:
    """Say that no context ceiling is set, because the gap is real (ADR-019).

    Without `context_tokens` the engine runs with its own default window, which is far
    smaller than most models support, and drops whatever does not fit without saying so.
    LACC cannot detect that; the least it can do is not let the gap be invisible.
    """
    console.print(
        "[yellow]No context ceiling set.[/yellow] Without `context_tokens` the engine "
        "uses its own default window and silently drops whatever does not fit. See "
        "`lacc profile` for what your model supports."
    )


def _write_or_exit(destination: Path, text: str) -> None:
    """Write a file LACC produced, and translate the one refusal it can meet.

    `write_new_file` refuses a path that already exists, which is the rule that keeps LACC
    from replacing something of yours. Three commands called it without catching that, so
    the refusal reached the terminal as a traceback - a deliberate, correct decision
    presented as a crash. Found by running `resolve` twice (ADR-087).
    """
    try:
        write_new_file(destination, text)
    except ConversionError as error:
        _show(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error


def _build_provider(choice: ProviderChoice, config: Config, skill: str = "") -> Provider:
    """Construct the chosen provider, for this skill's model.

    A configuration may name a model per skill and falls back to the one it always named
    (ADR-051). The routing is a table somebody wrote; nothing here chooses.
    """
    if choice is ProviderChoice.mock:
        return MockProvider()
    host = resolve_engine_host(config.engine_host, config.network_access)
    return OllamaProvider(config.model_for(skill), config.context_tokens, host)


def _say_which_model(config: Config, skill: str) -> None:
    """Say when a skill runs on a model other than the configured default.

    A run whose model came from a table is a run whose model the person should be told
    about, at the moment they are deciding whether to start it.
    """
    chosen = config.model_for(skill)
    if chosen and chosen != config.model:
        console.print(
            f"[yellow]{skill} runs on {chosen}[/yellow], not {config.model or 'the default'} - "
            "your configuration names a model for this skill."
        )


def _onto(status: object) -> ProgressFn:
    """Turn a Rich status line into something the cycle can report onto.

    The cycle knows how far along it is and nothing about terminals; this knows about
    terminals and nothing about runs. That separation is what lets an interface other than
    this one be written later without the behaviour moving into it.
    """

    def show(where: Progress) -> None:
        if where.stage == "asking" and where.total:
            status.update(  # type: ignore[attr-defined]
                f"Pass {where.done + 1} of {where.total} - {where.detail}"
            )
        elif where.stage == "dividing":
            status.update(f"Divided into {where.detail}")  # type: ignore[attr-defined]
        elif where.stage == "checking":
            status.update("Checking every quotation against the document...")  # type: ignore[attr-defined]

    return show


def _do_run(
    resolved: Skill,
    requests: tuple[str, ...],
    config: Config,
    workspace: Workspace,
    provider: Provider,
    audit: AuditLog,
    run_id: str,
    in_passes: bool = False,
    pages_per_pass: int | None = None,
    progress: ProgressFn | None = None,
) -> RunResult:
    """Run the skill through the cycle with confirmation already handled."""
    return run_skill(
        resolved,
        requests,
        grant_for(resolved, config),
        config,
        workspace,
        provider,
        audit,
        run_id,
        lambda _preview: True,
        _approve,
        in_passes,
        pages_per_pass,
        progress,
    )


_MANY_PASSES = 8
"""Passes beyond which a document is worth questioning rather than just running.

Eight is about a hundred pages at a 32k window - a guideline or a manual, not a paper.
"""


_OUTCOME_TAGS = {
    "completed": "white_check_mark",
    "refused": "no_entry",
    "declined": "raised_hand",
    "failed": "warning",
}


def _announce(
    skill_name: str,
    outcome: str,
    elapsed: float,
    config: Config,
    audit: AuditLog,
    run_id: str,
    body: str = "",
) -> None:
    """Tell the configured notifier that a run finished.

    Best effort: a notifier that cannot be built or cannot reach its server never fails a
    run that already happened (ADR-027). The message says which skill ran, how it ended and
    how long it took, and nothing else - not the paths, not the answer, not the error text.
    """
    try:
        notifier = notifier_from_config(config)
    except NotifierMisconfigured as error:
        audit.record(run_id, "notification_failed", "Notifier misconfigured", {"error": str(error)})
        console.print(f"[yellow]Notification not sent:[/yellow] {error}")
        return
    if notifier is None:
        return

    # The only witness to this trail that is not on this machine. A local tamperer can
    # rewrite the trail and its anchor; they cannot rewrite a notification already
    # delivered to a server somebody else keeps (ADR-049).
    anchor = check_anchor(audit.path)
    witness = (
        f" [trail: {anchor.found_records} records, {anchor.head[:8]}]" if anchor.present else ""
    )
    notification = Notification(
        title=f"LACC: {skill_name} {outcome}",
        body=(body or f"{skill_name} {outcome} after {elapsed:.0f}s") + witness,
        tags=(_OUTCOME_TAGS.get(outcome, "bell"),),
    )
    delivery = notifier.send(notification)
    audit.record(
        run_id,
        "notification_sent" if delivery.delivered else "notification_failed",
        f"Notification via {delivery.transport}: {delivery.detail}",
        {"transport": delivery.transport, "delivered": delivery.delivered},
    )
    if not delivery.delivered:
        console.print(
            f"[yellow]Notification not delivered[/yellow] ({delivery.transport}): {delivery.detail}"
        )


@app.command()
def preview(
    skill: Annotated[str, typer.Argument(help="Name of the skill to preview.")],
    requests: Annotated[
        list[str],
        typer.Argument(help="One or more paths inside the workspace."),
    ],
    config_path: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to the configuration file."),
    ] = DEFAULT_CONFIG_PATH,
) -> None:
    """Show what a skill would do, without asking, executing, or recording."""
    resolved = _resolve_skill(skill, config_path)
    config, workspace = _load(config_path)
    plan = _plan_or_exit(resolved, tuple(requests), config)
    result = preview_action(
        plan.action, grant_for(resolved, config), config, workspace, config.remote_engine
    )
    _show_preview(result)


_PAGE_RANGE = re.compile(r"^\s*(\d+)\s*(?:-\s*(\d+))?\s*$")


def _page_range(given: str | None) -> tuple[int, int] | None:
    """Read `40-68`, or `40` for a single page. Anything else is refused, not guessed."""
    if given is None:
        return None
    match = _PAGE_RANGE.match(given)
    if not match:
        raise typer.BadParameter(f"'{given}' is not a page or a range. Write 40 or 40-68.")
    first = int(match.group(1))
    last = int(match.group(2)) if match.group(2) else first
    if first < 1:
        raise typer.BadParameter("Pages are numbered from 1.")
    if first > last:
        raise typer.BadParameter(f"Page {first} comes after page {last}.")
    return first, last


@app.command()
def references(
    sources: Annotated[list[Path], typer.Argument(help="Documents inside the workspace.")],
    config_path: Annotated[
        Path, typer.Option("--config", "-c", help="Path to the configuration file.")
    ] = DEFAULT_CONFIG_PATH,
) -> None:
    """Report what more than one of these documents cites, and whether you hold it.

    Parsed from the reference list each document already carries. **No model and no
    network**: asked for reference metadata a model invents it - twelve journal names of
    twenty-four, with an instruction in the same prompt not to (ADR-047) - and the list is
    in the file, so there is nothing to generate.

    A work several of your papers cite is one the field treats as load-bearing. This counts;
    it does not judge. A work cited by three of them may be the thing all three disagree
    with (ADR-064).
    """
    _, workspace = _load(config_path)
    cited_by: dict[str, set[str]] = {}
    what: dict[str, str] = {}
    held: set[str] = set()
    parsed = silent = entries = 0

    for source in sources:
        try:
            path = workspace.resolve_within(source)
            text = path.read_text(encoding="utf-8", errors="replace")
        except (ValueError, OSError) as error:
            console.print(f"[red]{error}[/red]")
            continue
        # What this document says about itself, so "do I have it?" is answered against a
        # fact the file states rather than against a filename (ADR-047).
        own = (
            embedded_metadata(path.with_suffix(".pdf"))
            if path.with_suffix(".pdf").exists()
            else None
        )
        if own is not None and own.doi:
            held.add(own.doi.lower())

        found = references_in(text)
        entries += len(found)
        if found:
            parsed += 1
        else:
            silent += 1
            console.print(f"[dim]{source}: no numbered reference list found.[/dim]")
        for entry in found:
            if entry.doi:
                cited_by.setdefault(entry.doi.lower(), set()).add(str(source))
                # The first document to cite it supplies the words. They differ between
                # citation styles and any of them tells a reader what the work is, which
                # a DOI on its own does not.
                what.setdefault(entry.doi.lower(), as_one_line(entry))

    whole = without_truncations(frozenset(cited_by))
    shared = sorted(
        ((doi, cited_by[doi]) for doi in whole if len(cited_by[doi]) > 1),
        key=lambda pair: (-len(pair[1]), pair[0]),
    )

    console.print(
        f"[green]{parsed} of {parsed + silent} documents parsed[/green]; {entries} references, "
        f"{sum(len(v) for v in cited_by.values())} with a DOI."
    )
    if not shared:
        console.print("Nothing here is cited by more than one of them.")
        return

    console.print(f"[bold]{len(shared)} works cited by more than one:[/bold]")
    for doi, who in shared:
        # "not among yours" rather than "not held". Only the documents whose own DOI could
        # be read are comparable at all, and saying "not held" of a work sitting in the
        # workspace without a DOI in its metadata would be a false negative dressed as a
        # fact - the shape of error this project has corrected twelve times (ADR-064).
        mark = (
            "[green]you have this[/green]"
            if doi in held
            else "[yellow]not among the ones identifiable by DOI[/yellow]"
        )
        console.print(f"  [bold]{len(who)}x[/bold]  {what.get(doi, doi)[:150]}")
        console.print(f"        {doi}  {mark}")
        for name in sorted(who):
            console.print(f"        [dim]<- {name}[/dim]")
    console.print(
        f"[dim]{len(held)} of the documents given carry a DOI in their own metadata, so only "
        f"those could be matched against. Counted, not judged: a work several papers cite "
        f"may be the one they disagree with.[/dim]"
    )


@app.command()
def metadata(
    sources: Annotated[list[Path], typer.Argument(help="Documents inside the workspace.")],
    config_path: Annotated[
        Path, typer.Option("--config", "-c", help="Path to the configuration file.")
    ] = DEFAULT_CONFIG_PATH,
) -> None:
    """Print what each document says about itself: title, authors, DOI and date.

    No network and no model. Asked for a journal, a model supplied one from memory twelve
    times out of twenty-four **with an instruction in the same prompt not to** - and two
    were wrong in a way that would put a false citation in a thesis (ADR-047).

    The journal is not among the fields, and the DOI is why: with a correct identifier a
    reference manager resolves journal, volume and pages against a record rather than a
    recollection. What a file does not carry is reported as missing, never guessed.
    """
    _, workspace = _load(config_path)
    silent: list[str] = []
    for source in sources:
        try:
            path = workspace.resolve_within(source)
        except ValueError as error:
            console.print(f"[red]{error}[/red]")
            raise typer.Exit(code=1) from error
        if not path.exists():
            console.print(f"[red]{source} is not in the workspace.[/red]")
            raise typer.Exit(code=1)

        found = embedded_metadata(path)
        console.print(f"[bold]{source.name}[/bold]")
        if not found.says_anything:
            console.print("  [yellow]This file says nothing about itself.[/yellow]")
            silent.append(source.name)
            continue
        if found.title:
            console.print(f"  Title:   {found.title}")
        if found.authors:
            console.print(f"  Authors: {', '.join(found.authors)}")
        if found.doi:
            console.print(f"  DOI:     [bold]{found.doi}[/bold]")
        if found.date:
            console.print(f"  Date:    {found.date}")
        if found.missing:
            console.print(f"  [dim]Not in the file: {', '.join(found.missing)}[/dim]")

    if silent:
        console.print(
            f"[yellow]{len(silent)} of {len(sources)} carry no metadata at all.[/yellow] "
            "Preprints, statistics sheets and some guidelines ship without it. Nothing here "
            "will invent it for you, which is the point."
        )


@app.command()
def resolve(
    sources: Annotated[list[Path], typer.Argument(help="Documents inside the workspace.")],
    into: Annotated[Path, typer.Option("--into", help="Where to write the bibliography.")],
    cited: Annotated[
        bool, typer.Option("--cited", help="Also resolve the DOIs these documents cite.")
    ] = False,
    config_path: Annotated[
        Path, typer.Option("--config", "-c", help="Path to the configuration file.")
    ] = DEFAULT_CONFIG_PATH,
) -> None:
    """Ask a registry what each work is, using the DOI the document already carries.

    **The one command here that talks to something that is not yours.** What leaves is a
    DOI and nothing else: no document, no quotation, no corpus, no question and no text you
    wrote. You are shown how many are about to be sent, and where, before any of them go.

    Two switches have to be on - `network_access` and `registry_url` - and both are off by
    default. Answers are kept beside the file written, so a DOI is never asked twice and a
    bibliography can be rebuilt from what was actually received (ADR-067).
    """
    config, workspace = _load(config_path)
    if not config.registry_url:
        _show(
            "[red]No registry is configured.[/red] Write `registry_url: https://api.crossref.org` "
            "in your configuration. It is empty by default, and empty means nothing leaves "
            "this machine."
        )
        raise typer.Exit(code=1)
    if not config.network_access:
        _show(
            "[red]network_access is off.[/red] It is the ceiling, and a registry address "
            "does not lift it. Both have to be on, deliberately."
        )
        raise typer.Exit(code=1)

    wanted: dict[str, str] = {}
    silent: list[str] = []
    for source in sources:
        try:
            path = workspace.resolve_within(source)
        except ValueError as error:
            _show(f"[red]{error}[/red]")
            raise typer.Exit(code=1) from error
        if not path.exists():
            _show(f"[red]{source} is not in the workspace.[/red]")
            raise typer.Exit(code=1)
        own = embedded_metadata(path).doi
        stated = established_for(path)
        if own:
            wanted.setdefault(own.strip().lower(), source.name)
        elif stated is not None:
            # Established by a person and recorded beside the file, because no test tried
            # separates a document's own printed DOI from one it cites (ADR-087).
            wanted.setdefault(stated.doi.strip().lower(), f"{source.name} (established)")
        else:
            silent.append(source.name)
        if cited:
            text = path.read_text(encoding="utf-8", errors="replace")
            found = frozenset(r.doi for r in references_in(text) if r.doi)
            for doi in without_truncations(found):
                wanted.setdefault(doi, f"cited by {source.name}")

    if not wanted:
        # The first run of this found the reason the hard way: a document's own DOI lives in
        # the PDF's metadata, and a workspace holds the Markdown that was converted from it.
        # Saying "carries no DOI" was true and useless (ADR-067).
        converted = sum(1 for source in sources if source.suffix == ".md")
        _show("[yellow]No DOI to resolve.[/yellow] Nothing here will invent one.")
        if converted and not cited:
            _show(
                f"[dim]{converted} of these are Markdown. A document's own DOI is in the "
                "PDF's metadata and does not survive conversion - run this on the PDFs, or "
                "add --cited to resolve what they cite instead.[/dim]"
            )
        elif cited:
            _show(
                "[dim]Their reference lists carry no recoverable DOI. Most journals print "
                "none: measured at 225 of 2,315 references, about one in eleven "
                "(ADR-064).[/dim]"
            )
        raise typer.Exit(code=1)

    destination = workspace.resolve_within(into)
    remembered = destination.with_suffix(".registry.json")
    registry = RememberedRegistry(
        CrossrefRegistry(config.registry_url, config.registry_mailto), remembered
    )
    fresh = sorted(doi for doi in wanted if not registry.holds(doi))

    _show(
        f"[bold]{len(wanted)} DOIs[/bold], of which {len(wanted) - len(fresh)} are already known."
    )
    if fresh:
        _show(
            f"[yellow]{len(fresh)} would be sent to {config.registry_url}.[/yellow] "
            "A DOI is public; the list of them is your bibliography."
        )
        if config.registry_mailto:
            _show(f"Identifying you as [bold]{config.registry_mailto}[/bold], as configured.")
        if not typer.confirm("Send them?", default=False):
            _show("Nothing was sent.")
            raise typer.Exit(code=1)

    resolved: list[Work] = []
    unknown: list[str] = []
    repaired = 0
    for doi in sorted(wanted):
        try:
            answer = registry.about(doi)
        except RegistryError as error:
            _show(f"[red]{error}[/red]")
            _show("Nothing was written. What had been answered is kept, so a retry asks less.")
            registry.write()
            raise typer.Exit(code=1) from error
        if answer is None:
            # The registry does not hold it. Where the string shows evidence of having
            # something stuck to it - a second DOI, a run-on word - try the cut and let the
            # registry decide. A merely truncated DOI offers no cuts (ADR-083).
            for cut in shortened(doi):
                try:
                    answer = registry.about(cut)
                except RegistryError:
                    break
                if answer and answer.says_anything:
                    repaired += 1
                    break
        if answer and answer.says_anything:
            resolved.append(answer)
        else:
            unknown.append(doi)
    registry.write()

    _write_or_exit(destination, bibliography(resolved, unknown, silent, config.registry_url))
    _show(f"[green]{len(resolved)} of {len(wanted)} resolved[/green] -> {into}")
    if repaired:
        _show(
            f"[dim]{repaired} were recovered by cutting what extraction had stuck to them, "
            "and the registry confirmed each cut.[/dim]"
        )
    if unknown:
        _show(f"[yellow]{len(unknown)} the registry does not hold.[/yellow] Usually a mangled DOI.")
    if silent:
        _show(f"[dim]{len(silent)} documents carry no DOI of their own.[/dim]")


@app.command()
def outline(
    source: Annotated[Path, typer.Argument(help="A document inside the workspace.")],
    config_path: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to the configuration file."),
    ] = DEFAULT_CONFIG_PATH,
    about: Annotated[
        str | None,
        typer.Option(
            "--about",
            help="Show only sections whose title contains one of these words, comma separated.",
        ),
    ] = None,
) -> None:
    """List a document's sections and the page each starts on, so you can choose one.

    Nothing is sent anywhere and no model is involved. Choosing what to read is the step
    before reading, and a model asked to choose would leave things out without saying which
    - measured behaviour, and the reason this is string matching (ADR-046).

    Two sources, in order. A PDF's own embedded outline is the document's structure rather
    than a guess at it, and most published papers carry one. When there is none, numbered
    headings are found in the text, which is what guidelines and theses have.
    """
    config, workspace = _load(config_path)
    try:
        resolved = workspace.resolve_within(source)
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error
    if not resolved.exists():
        console.print(f"[red]{source} is not in the workspace.[/red]")
        raise typer.Exit(code=1)

    found = embedded_outline(resolved) if resolved.suffix.lower() == ".pdf" else ()
    how = "the document's own outline"
    if not found:
        text = _text_to_outline(resolved, config)
        found = headings_in(text)
        how = "numbered headings found in the text"
    if not found:
        console.print(
            f"[yellow]No sections found in {source.name}.[/yellow] It carries no outline, and "
            "its headings are not numbered - so there is nothing here that can be located "
            "without guessing at how lines were typed."
        )
        raise typer.Exit(code=1)

    sections = tuple(h for h in found if not h.in_contents)
    contents = len(found) - len(sections)
    shown = sections
    if about:
        words = tuple(word.strip() for word in about.split(",") if word.strip())
        shown = matching(sections, words)

    console.print(f"[bold]{source.name}[/bold] - {len(sections)} sections, from {how}.")
    if contents:
        console.print(f"{contents} more are lines from its table of contents, not shown.")
    for heading in shown:
        indent = "  " * min(heading.depth, 5)
        number = f"{heading.number} " if heading.number else ""
        console.print(f"  [dim]p.{heading.page:>4}[/dim]  {indent}{number}{heading.title}")

    if about:
        # Said whichever way it came out. A filter that shows its hits and hides its
        # count is the invisible omission this command exists to avoid.
        console.print(
            f"[yellow]{len(sections) - len(shown)} of {len(sections)} sections are hidden "
            f"by --about.[/yellow] Run without it to see them; the words are yours, and a "
            "section can be about a subject without being named for it."
        )


def _text_to_outline(path: Path, config: Config) -> str:
    """Return the document's text, converting it in memory when it is not already text.

    Reads without writing: listing what is in a document should not leave a file behind.
    """
    if path.suffix.lower() in {".md", ".txt"}:
        return path.read_text(encoding="utf-8", errors="replace")
    try:
        return converter_for(path).extract_text(path)
    except ConversionError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error


@app.command()
def ingest(
    sources: Annotated[
        list[Path],
        typer.Argument(help="Documents to convert (PDF or .docx), inside the workspace."),
    ],
    destination: Annotated[
        Path | None,
        typer.Option("--into", help="Where to write the text. Only valid for one document."),
    ] = None,
    config_path: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to the configuration file."),
    ] = DEFAULT_CONFIG_PATH,
    pages: Annotated[
        str | None,
        typer.Option(
            "--pages",
            help=(
                "Take only these pages, as 40-68 or 40. The document's own numbering is "
                "kept, so what you take from page 40 still cites as page 40."
            ),
        ),
    ] = None,
) -> None:
    """Extract documents' text into files LACC can read, after preview and confirmation.

    Several documents at once, because a bibliography is not read one confirmation at a
    time: collecting across twenty-three papers began with twenty-three prompts before any
    work started. One preview names every document and every file it would write.

    Each conversion is still its own run in the audit, and one that fails costs that
    document rather than the batch.
    """
    if destination is not None and len(sources) != 1:
        console.print(
            "[red]--into names one file, so it works with one document.[/red] Without it "
            "each document is written beside itself with a .md suffix."
        )
        raise typer.Exit(code=1)

    config, workspace = _load(config_path)
    audit = AuditLog(workspace, config)

    jobs: list[tuple[Path, Path, Converter]] = []
    for source in sources:
        target = destination if destination is not None else source.with_suffix(".md")
        try:
            jobs.append((source, target, converter_for(source)))
        except ConversionError as error:
            console.print(f"[red]{error}[/red]")
            raise typer.Exit(code=1) from error

    action = IntendedAction(
        name="ingest",
        summary=(
            f"Extract the text of {sources[0]} into {jobs[0][1]}"
            if len(jobs) == 1
            else f"Extract the text of {len(jobs)} documents"
        ),
        required=frozenset({"read_files", "write_files"}),
        targets=tuple(source for source, _, _ in jobs),
        writes=tuple(target for _, target, _ in jobs),
    )
    preview = preview_action(action, grant(action.required, config), config, workspace)
    _show_preview(preview)
    if not preview.allowed:
        _exit_refused()
    question = "Proceed?" if len(jobs) == 1 else f"Convert {len(jobs)} documents?"
    if not typer.confirm(question, default=False):
        console.print("[yellow]Declined.[/yellow] Nothing was written.")
        return

    wanted = _page_range(pages)

    done, failed = 0, []
    for source, target, converter in jobs:
        try:
            result = run_conversion(
                action.model_copy(update={"targets": (source,), "writes": (target,)}),
                source,
                target,
                converter,
                grant(action.required, config),
                config,
                workspace,
                audit,
                new_run_id(),
                lambda _preview: True,
                wanted,
            )
        except (ConversionError, PageRangeError) as error:
            # One unreadable document costs that document, not the batch.
            failed.append((source, str(error)))
            continue
        if result.outcome == "completed":
            done += 1
            _report_ingestion(
                result,
                target,
                getattr(converter, "furniture_dropped", 0),
                getattr(converter, "hidden", ()),
            )

    if len(jobs) > 1:
        console.print(Panel(f"{done} of {len(jobs)} documents converted", title="Ingested"))
    for source, message in failed:
        console.print(f"[yellow]{source}:[/yellow] {message}")

    # A batch that converted something reports what failed and exits zero; one that
    # converted nothing failed, and a script checking the exit code must be told (ADR-017).
    if failed and not done:
        raise typer.Exit(code=1)


def _report_hidden_text(hidden: tuple[HiddenText, ...], fragments: int = 0) -> None:
    """Show text a reader could not have seen, without judging what it is.

    A scanned document is entirely an invisible layer over the image a person reads, and
    that is correct. An ordinary paper with three invisible lines is not. LACC cannot tell
    them apart and the user can, so this reports and does not decide (ADR-040).

    It matters because the grounding check is no help here: a quotation of hidden text
    verifies, since the text genuinely is in the document.
    """
    if not hidden:
        return
    console.print(
        f"[yellow]{len(hidden)} of {fragments or len(hidden)} pieces of text in this "
        "document are not visible to a reader.[/yellow] Most of a document being invisible "
        "describes its layout - a scan, a wide infographic. A handful in a typeset paper "
        "describes something else."
    )
    for item in hidden[:8]:
        where = f"p. {item.page}, {item.reason}"
        console.print(
            f"  [dim]{where}[/dim] {item.text[:90]}" if item.text else f"  [dim]{where}[/dim]"
        )
    if len(hidden) > 8:
        console.print(f"  [dim]and {len(hidden) - 8} more[/dim]")
    console.print(
        "[dim]Checking quotations is no defence against this: text hidden in the document "
        "is in the document, so a quotation of it verifies.[/dim]"
    )


def _report_ingestion(
    result: RunResult,
    destination: Path,
    furniture: int = 0,
    hidden: tuple[HiddenText, ...] = (),
    fragments: int = 0,
) -> None:
    """Print the outcome of an ingestion run, naming the file it produced.

    Says how many lines were dropped as page furniture. Ingestion edits rather than only
    transcribing now, and a heuristic that quietly deletes text from a document the user
    keeps is the wrong shape for this project (ADR-036).
    """
    if result.outcome == "completed":
        console.print(Panel(f"Extracted text written to {destination}", title="Ingested"))
        if furniture:
            console.print(
                f"[dim]{furniture} lines were dropped as page furniture - running headers, "
                "footers and page numbers repeated across pages.[/dim]"
            )
        _report_hidden_text(hidden, fragments)
    elif result.outcome == "refused":
        _exit_refused()
    else:
        console.print("[yellow]Declined.[/yellow] Nothing was written.")


@app.command()
def measure(
    skill: Annotated[str, typer.Argument(help="Name of the skill to measure.")],
    requests: Annotated[
        list[str],
        typer.Argument(help="One or more paths inside the workspace."),
    ],
    runs: Annotated[
        int,
        typer.Option("--runs", "-n", min=2, max=25, help="How many times to run it."),
    ] = 5,
    config_path: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to the configuration file."),
    ] = DEFAULT_CONFIG_PATH,
    provider_choice: Annotated[
        ProviderChoice,
        typer.Option("--provider", help="Which provider to run against."),
    ] = ProviderChoice.ollama,
    corpus_file: Annotated[
        Path | None,
        typer.Option(
            "--from",
            help="Measure ask_corpus instead: the argument is the question, this is the corpus.",
        ),
    ] = None,
) -> None:
    """Run a skill several times and report the spread, not a single number.

    Measuring is a different act from running: it characterises a configuration rather than
    doing work, so it refuses any skill that writes and never varies the action between
    repetitions (ADR-032). One preview, one confirmation, covering all of them.
    """
    # Not resolved by name when a corpus is given: ask_corpus is deliberately absent from
    # the registry, because `lacc run ask_corpus <path>` would send a prompt with the
    # passages hole unfilled. It is reached through `ask` and through here, and nowhere else.
    if corpus_file is not None and skill != AskCorpusSkill().name:
        console.print(
            f"[red]--from measures ask_corpus, not {skill}.[/red] Write "
            '`lacc measure ask_corpus "your question" --from corpus.md`.'
        )
        raise typer.Exit(code=1)
    resolved = AskCorpusSkill() if corpus_file is not None else _resolve_skill(skill, config_path)
    if "write_files" in resolved.required:
        console.print(
            f"[red]{skill} writes files, and measuring must not act.[/red] Repeating an "
            "action that has effects would multiply them; a measurement only observes."
        )
        raise typer.Exit(code=1)

    config, workspace = _load(config_path)
    audit = AuditLog(workspace, config)
    try:
        provider = _build_provider(provider_choice, config, resolved.name)
    except ProviderError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    plan = _plan_or_exit(resolved, tuple(requests), config)

    # Measuring the synthesis path: the argument is the question and --from is the corpus.
    # The passages are chosen once and reused across every run, so what varies between them
    # is the model and not the selection.
    material: str | None = None
    if corpus_file is not None:
        made = _prepared_or_exit(requests[0], corpus_file, config, workspace)
        material = made.material
        plan = _plan_or_exit(resolved, (requests[0],), config)
    preview = preview_action(
        plan.action, grant_for(resolved, config), config, workspace, config.remote_engine
    )
    _show_preview(preview)
    if not preview.allowed:
        _exit_refused()
    # The confirmation is for the repetition, not for one action with a multiplier hidden
    # behind it: the person is told how many times before being asked.
    if not typer.confirm(f"Run this {runs} times, plus one warm-up?", default=False):
        console.print("[yellow]Declined.[/yellow] Nothing was run.")
        return

    rows: list[tuple[int, int, int]] = []
    # The first run after an engine loads a model differs from the ones after it, reliably
    # enough that it was once read as the model being non-deterministic at temperature
    # zero. It is discarded rather than annotated: a measurement with a known contaminant
    # should remove it (ADR-037).
    with console.status(f"Measuring {resolved.name}...") as status:
        for attempt in range(0, runs + 1):
            status.update("Warming up..." if attempt == 0 else f"Run {attempt} of {runs}...")
            try:
                if material is None:
                    result = _do_run(
                        resolved, tuple(requests), config, workspace, provider, audit, new_run_id()
                    )
                else:
                    result = ask_once(
                        resolved, plan, material, config, workspace, provider, audit, new_run_id()
                    )
            except (ProviderError, ReadError, PromptTooLargeError) as error:
                where = "The warm-up run" if attempt == 0 else f"Run {attempt}"
                console.print(f"[red]{where} failed:[/red] {error}")
                raise typer.Exit(code=1) from error
            if attempt == 0:
                continue
            # Synthesis is checked against what was sent, not against a document: what is in
            # doubt is whether the model quoted what it was shown or what it remembers.
            checked = (
                result.checked_claims
                if material is None
                else without_repeats(
                    check_answer(
                        result.completion.text if result.completion else "",
                        material,
                        plan.fields,
                        plan.quote_field,
                    )
                )
            )
            # Counted by whether the quotation is in the document. `holds` also requires a
            # page, which measures LACC's ability to place it rather than the model's
            # fidelity - and mixing the two is what made a corpus of real quotations look
            # like a third fabricated (ADR-042).
            rows.append((attempt, len(checked), sum(1 for c in checked if c.found)))

    _report_thespread(resolved.name, config.model, rows)


def _report_thespread(skill_name: str, model: str, rows: list[tuple[int, int, int]]) -> None:
    """Show every run, then the range each column covered."""
    table = Table(title=f"{skill_name} against {model or 'the mock provider'}", expand=False)
    table.add_column("Run", justify="right")
    table.add_column("Quotations", justify="right")
    table.add_column("In the document", justify="right")
    table.add_column("Rate", justify="right")
    for attempt, total, held in rows:
        rate = f"{held * 100 // total}%" if total else "-"
        table.add_row(str(attempt), str(total), str(held), rate)
    console.print(table)

    totals = [total for _, total, _ in rows]
    verified = [held for _, _, held in rows]
    rates = [held * 100 // total for _, total, held in rows if total]
    console.print(f"  quotations  {spread(totals)}")
    console.print(f"  in the document  {spread(verified)}")
    console.print(f"  rate        {spread(rates)}")

    if rates and max(rates) - min(rates) >= 10:
        console.print()
        console.print(
            f"[yellow]This configuration varied by {max(rates) - min(rates)} points "
            f"across {len(rows)} runs.[/yellow] A single run would not have told you "
            "that, and cannot be compared against another single run."
        )


def _announce_the_traverse(
    skill_name: str,
    gathered: list[tuple[str, RunResult | str]],
    started: float,
    config: Config,
    audit: AuditLog,
    outcome: str,
) -> None:
    """Say that a traverse across many documents finished, and what it found.

    The body carries counts rather than names. How many papers somebody read is a smaller
    disclosure than which ones, and a notification travels further than a terminal does -
    even to a server you host yourself (ADR-027).
    """
    done = [outcome_ for _, outcome_ in gathered if isinstance(outcome_, RunResult)]
    quotations = sum(len(result.checked_claims) for result in done)
    found = sum(1 for result in done for claim in result.checked_claims if claim.found)
    body = (
        f"{len(done)} of {len(gathered)} documents, {found} of {quotations} quotations in "
        f"their source, after {(time.monotonic() - started) / 60:.0f} min"
    )
    _announce(skill_name, outcome, time.monotonic() - started, config, audit, new_run_id(), body)


@app.command()
def collect(
    skill: Annotated[str, typer.Argument(help="Name of the skill to run on each document.")],
    requests: Annotated[list[str], typer.Argument(help="Paths inside the workspace.")],
    into: Annotated[Path, typer.Option("--into", help="Where to write the collected results.")],
    config_path: Annotated[
        Path, typer.Option("--config", "-c", help="Path to the configuration file.")
    ] = DEFAULT_CONFIG_PATH,
    provider_choice: Annotated[
        ProviderChoice, typer.Option("--provider", help="Which provider to run against.")
    ] = ProviderChoice.ollama,
    in_passes: Annotated[
        bool,
        typer.Option(
            "--in-passes",
            help="Read documents in several passes over their pages. Needed for one too "
            "large for the window, and worth it for one that fits: measured at six "
            "times the quotations, because a prompt asks once however much it is "
            "shown (ADR-089).",
        ),
    ] = False,
    pages_per_pass: Annotated[
        int | None,
        typer.Option(
            "--pages-per-pass",
            min=1,
            help=(
                "Read in passes of this many pages, even when the document "
                "fits. Measured: about three pages gave 4.6x the verified "
                "quotations for twice the time."
            ),
        ),
    ] = None,
) -> None:
    """Run a skill across many documents, one at a time, and collect what it found.

    A library does not fit in a context window - thirty papers are twelve times the budget
    of the largest one this hardware can run. Each document therefore gets the whole window
    to itself, which also makes it impossible for a quotation to be attributed to the wrong
    paper: the source is a fact about which run produced it (ADR-039).
    """
    resolved = _resolve_skill(skill, config_path)
    config, workspace = _load(config_path)
    if not resolved.plan((requests[0],), config).verify_quotes:
        console.print(
            f"[red]{skill} does not check its quotations, so there is nothing to collect "
            "that could be trusted.[/red] A long file of unchecked prose is no better than "
            "the model that wrote it."
        )
        raise typer.Exit(code=1)

    audit = AuditLog(workspace, config)
    try:
        provider = _build_provider(provider_choice, config, resolved.name)
    except ProviderError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    destination = workspace.resolve_within(into)
    action = IntendedAction(
        name="collect",
        summary=f"Collect {skill} from {len(requests)} documents into {into}",
        required=frozenset({"read_files", "write_files"}),
        targets=tuple(Path(item) for item in requests),
        writes=(Path(into),),
    )
    preview = preview_action(
        action, grant(action.required, config), config, workspace, config.remote_engine
    )
    _show_preview(preview)
    if not preview.allowed:
        _exit_refused()
    if not typer.confirm(f"Read {len(requests)} documents and write {into}?", default=False):
        console.print("[yellow]Declined.[/yellow] Nothing was run.")
        return

    started = time.monotonic()
    gathered: list[tuple[str, RunResult | str]] = []
    with console.status("Collecting...") as status:
        for index, request in enumerate(requests, start=1):
            status.update(f"{request} ({index} of {len(requests)})...")
            try:
                gathered.append(
                    (
                        request,
                        _do_run(
                            resolved,
                            (request,),
                            config,
                            workspace,
                            provider,
                            audit,
                            new_run_id(),
                            in_passes,
                            pages_per_pass,
                        ),
                    )
                )
            except (
                ProviderError,
                ReadError,
                PromptTooLargeError,
                CannotReadInPasses,
            ) as error:
                # One unreadable file should cost one document, not the traverse (ADR-039).
                gathered.append((request, str(error)))

    try:
        write_new_file(destination, collected_markdown(resolved.name, config.model, gathered))
    except ConversionError as error:
        _announce_the_traverse(resolved.name, gathered, started, config, audit, "failed")
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    # The command that runs for an hour is the one that most needs to say it finished, and
    # until now it was the only long one that did not.
    _announce_the_traverse(resolved.name, gathered, started, config, audit, "completed")

    failed = [name for name, outcome in gathered if isinstance(outcome, str)]
    verified = sum(
        sum(1 for c in outcome.checked_claims if c.found)
        for _, outcome in gathered
        if not isinstance(outcome, str)
    )
    total = sum(
        len(outcome.checked_claims) for _, outcome in gathered if not isinstance(outcome, str)
    )
    console.print(
        Panel(
            f"{verified} of {total} quotations are in their document, written to {into}",
            title="Collected",
        )
    )
    if failed:
        console.print(
            f"[yellow]{len(failed)} documents were not collected:[/yellow] {', '.join(failed)}"
        )


def _corpus_skill(name: str, config_path: Path) -> Skill:
    """Resolve a declared skill and insist that it works over a corpus.

    A declaration meant for a document would be handed passages where it expects a file, and
    would answer confidently about the wrong shape of material. Refusing is cheap; noticing
    afterwards is not.
    """
    skill = _resolve_skill(name, config_path)
    declared = getattr(skill, "declared", None)
    if declared is None or not declared.over_a_corpus:
        console.print(
            f"[red]{name} does not work over a corpus.[/red] A skill used with --using must "
            "declare `over: corpus`, because it is handed retrieved passages rather than a "
            "file it named."
        )
        raise typer.Exit(code=1)
    return skill


@app.command()
def ask(
    question: Annotated[str, typer.Argument(help="What you want answered.")],
    corpus_file: Annotated[
        Path, typer.Option("--from", help="A corpus written by lacc collect or lacc corpus.")
    ],
    config_path: Annotated[
        Path, typer.Option("--config", "-c", help="Path to the configuration file.")
    ] = DEFAULT_CONFIG_PATH,
    provider_choice: Annotated[
        ProviderChoice, typer.Option("--provider", help="Which provider to run against.")
    ] = ProviderChoice.ollama,
    using: Annotated[
        str | None,
        typer.Option(
            "--using",
            help="A declared skill that works over a corpus, instead of the built-in answer.",
        ),
    ] = None,
    judge: Annotated[
        bool,
        typer.Option(
            "--judge",
            help="Also ask whether each reading follows from the words it rests on. "
            "One extra engine call per claim, and a judgement rather than a check.",
        ),
    ] = False,
) -> None:
    """Answer a question from passages already checked against their documents.

    A corpus of six hundred quotations does not fit a context window, so something has to
    choose what goes in. That choosing discards material on your behalf, which is why this
    says how much it set aside before it asks anything (ADR-050).

    Only passages that were found in the document they name are eligible, and the answer's
    own quotations are checked again against the passages it was given. A model that quotes
    something it remembers rather than something it was shown is caught by that.
    """
    config, workspace = _load(config_path)
    audit = AuditLog(workspace, config)
    made = _prepared_or_exit(question, corpus_file, config, workspace)
    chosen_by = _retriever_for(config, workspace.resolve_within(corpus_file))

    resolved: Skill = AskCorpusSkill()
    if using is not None:
        resolved = _corpus_skill(using, config_path)
    plan = _plan_or_exit(resolved, (question,), config)
    preview = preview_action(
        plan.action, grant_for(resolved, config), config, workspace, config.remote_engine
    )
    _say_which_model(config, resolved.name)
    if not _confirm(preview):
        console.print("[yellow]Declined.[/yellow] Nothing was run.")
        return

    try:
        provider = _build_provider(provider_choice, config, resolved.name)
    except ProviderError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    run_id = new_run_id()
    audit.record(
        run_id,
        "passages_selected",
        f"Selected {made.selected} of {made.considered} passages",
        {
            "question": question,
            "retriever": made.how,
            "selected": made.selected,
            "set_aside": made.set_aside,
            "considered": made.considered,
        },
    )

    material = made.material
    started = time.monotonic()
    try:
        with console.status("Asking..."):
            result = ask_once(resolved, plan, material, config, workspace, provider, audit, run_id)
    except (ProviderError, PromptTooLargeError) as error:
        _announce(resolved.name, "failed", time.monotonic() - started, config, audit, run_id)
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    _announce(resolved.name, result.outcome, time.monotonic() - started, config, audit, run_id)
    if result.completion is not None:
        _show(result.completion.text)
    _check_against_what_was_sent(
        result,
        material,
        plan,
        audit,
        run_id,
        provider if judge else None,
        made.chosen,
        chosen_by,
    )
    console.print(
        f"[dim]{made.set_aside} of {made.considered} passages were not sent. An "
        "answer drawn from a selection is an answer about that selection.[/dim]"
    )


def _retriever_for(config: Config, corpus: Path | None) -> Retriever:
    """The word ranking, or both rankings fused, depending on the configuration.

    Word ranking stays the default. Naming an embedding model adds meaning to it rather
    than replacing it: the two find different things, and the fused ranking holds both
    (ADR-061). The vectors are remembered beside the corpus, which is what makes a second
    question cost milliseconds instead of the forty-eight seconds the first one did.
    """
    words = WordRetriever()
    if not config.embedding_model:
        return words
    # The same host rule as generation, and for the same reason: an environment variable
    # may only ever point at this machine, and anywhere else has to be written down.
    host = resolve_engine_host(config.engine_host, config.network_access)
    embedder = OllamaEmbedder(config.embedding_model, host)
    cache = corpus.with_suffix(corpus.suffix + VECTOR_SUFFIX) if corpus else None
    return FusedRetriever(words, DenseRetriever(embedder, cache))


def _prepared_or_exit(
    question: str, corpus_file: Path, config: Config, workspace: Workspace
) -> Prepared:
    """Rank a corpus against a question, say what was chosen, or exit saying why not.

    **The one path `ask`, `measure` and the window all take.** Three copies of this decision
    existed - two here and one in the slice - and the rule that should have caught it did
    not, because one of them mentioned a variable named `corpus` and that is also the name
    of a command that prints (ADR-086).
    """
    try:
        resolved = workspace.resolve_within(corpus_file)
        text = resolved.read_text(encoding="utf-8", errors="replace")
    except (ValueError, OSError) as error:
        console.print(f"[red]Cannot read {corpus_file}: {error}[/red]")
        raise typer.Exit(code=1) from error
    made = prepare(question, corpus_file.name, text, config, _retriever_for(config, resolved))
    if made.refusal:
        # Includes a ranking that could not be made: refused rather than quietly falling back
        # to words, because a selection made by a different method is a different answer and
        # saying so afterwards is worse than not answering (ADR-061).
        console.print(f"[red]{made.refusal}[/red]")
        raise typer.Exit(code=1)
    console.print(
        f"[green]{made.selected} passages selected[/green] of {made.considered}; "
        f"{made.set_aside} set aside. [dim]{made.how}[/dim]"
    )
    return made


def _judge_the_readings(
    checked: tuple[CheckedClaim, ...],
    provider: Provider,
    plan: SkillPlan,
    audit: AuditLog,
    run_id: str,
    passages: tuple[Passage, ...] = (),
    retriever: Retriever | None = None,
) -> None:
    """Ask whether each verified quotation supports the reading made of it (ADR-053).

    Only the quotations that were found: a reading resting on words the model invented is
    already reported, and judging it would say the same thing twice in a weaker voice.

    **Leads with the binary and gives the label beside it.** Graded on eight pairs labelled
    first, this judge got the three-way label right 6 times and *should a person look at
    this* right 8 times out of 8, with no false alarm on the three that were fine. Both its
    errors arrived with correct reasoning attached to the wrong label, so the reliable half
    goes first.
    """
    real = tuple(claim for claim in checked if claim.found)
    if not real:
        return
    judge = AskingJudge(provider)
    verdicts = []
    with console.status(f"Judging {len(real)} readings..."):
        for claim in real:
            verdicts.append((claim, judge.judge(claim.claim.claim, claim.claim.quote)))

    flagged = [(c, v) for c, v in verdicts if v.worth_a_look]
    undecided = sum(1 for _, v in verdicts if v.verdict == "undecided")
    # One record for the batch, carrying a row per reading: what was judged, what was
    # asked, and what came back, all by digest. These calls are deliberately not
    # `provider_called` - that record carries the cycle's per-call token estimate beside
    # the engine's measurement (ADR-020), and nothing outside the cycle has the estimate.
    # Digests always, the judge's words only under `full`, the rule every content follows.
    judged_rows = [
        {
            "quote_sha256": digest_of(claim.claim.quote),
            "claim_sha256": digest_of(claim.claim.claim),
            "asked_sha256": digest_of(verdict.asked),
            "verdict": verdict.verdict,
        }
        for claim, verdict in verdicts
    ]
    audit.record(
        run_id,
        "readings_judged",
        f"Judged {len(real)} readings for {plan.action.name}",
        {
            "action": plan.action.name,
            "judge": judge.name,
            "judged": len(real),
            "worth_a_look": len(flagged),
            "undecided": undecided,
            "judged_readings": judged_rows,
            "completion": [
                {"verdict": verdict.verdict, "why": verdict.detail} for _, verdict in verdicts
            ],
        },
    )

    console.print(
        "[dim]A model judging a model. The quotation check compares strings and has no "
        "opinion; this has one, and can be wrong in both directions (ADR-053).[/dim]"
    )
    if not flagged:
        console.print(
            f"[green]All {len(real)} readings were judged to follow from their quotations.[/green]"
        )
    else:
        console.print(
            f"[yellow]{len(flagged)} of {len(real)} readings are worth reading before you "
            f"cite them.[/yellow]"
        )
        for claim, verdict in flagged:
            console.print(f"  [yellow]?[/yellow] {claim.claim.claim[:95]}")
            console.print(f"    [dim]{verdict.verdict}: {verdict.detail[:110]}[/dim]")
            if retriever is None:
                continue
            for candidate in might_support(
                claim.claim.claim, claim.claim.quote, passages, retriever
            ):
                where = (
                    f"{candidate.source}, p. {candidate.page}"
                    if candidate.page
                    else candidate.source
                )
                console.print(f"    [dim]could support it: {candidate.text[:95]}[/dim]")
                console.print(f"    [dim]                  [{where}][/dim]")
    if undecided:
        console.print(f"[dim]{undecided} could not be judged, and that is not approval.[/dim]")


def _check_against_what_was_sent(
    result: RunResult,
    material: str,
    plan: SkillPlan,
    audit: AuditLog,
    run_id: str,
    provider: Provider | None = None,
    passages: tuple[Passage, ...] = (),
    retriever: Retriever | None = None,
) -> None:
    """Check the answer's quotations against the passages it was given, not the documents.

    The passages were already checked against their documents when the corpus was built. What
    is unknown here is whether the model quoted what it was shown or something it remembers,
    and the material it was shown is what answers that.
    """
    if result.completion is None:
        return
    checked = without_repeats(
        check_answer(result.completion.text, material, plan.fields, plan.quote_field)
    )
    if not checked:
        console.print(
            "[yellow]No quotations to check.[/yellow] The answer did not use the format, so "
            "nothing in it was verified."
        )
        return
    invented = [c for c in checked if not c.found]
    audit.record(
        run_id,
        "quotations_checked",
        f"Checked {len(checked)} quotations against the passages sent",
        {
            "action": plan.action.name,
            "quotations": len(checked),
            "verified": len(checked) - len(invented),
            "not_in_the_document": len(invented),
        },
    )
    if not invented:
        console.print(
            f"[green]All {len(checked)} quotations are in the passages that were sent.[/green]"
        )
        if provider is not None:
            _judge_the_readings(checked, provider, plan, audit, run_id, passages, retriever)
        return
    console.print(
        f"[red]{len(invented)} of {len(checked)} quotations are not in what was sent.[/red] "
        "The model quoted something it was not shown. Do not cite these without opening the "
        "document."
    )
    for claim in invented:
        console.print(f"  [red]x[/red] {claim.claim.quote[:100]}")
    if provider is not None:
        _judge_the_readings(checked, provider, plan, audit, run_id, passages, retriever)


@app.command()
def corpus(
    sources: Annotated[list[Path], typer.Argument(help="Corpus files written by lacc collect.")],
    into: Annotated[Path, typer.Option("--into", help="Where to write the assembled corpus.")],
    config_path: Annotated[
        Path, typer.Option("--config", "-c", help="Path to the configuration file.")
    ] = DEFAULT_CONFIG_PATH,
    about_words: Annotated[
        str | None,
        typer.Option(
            "--about",
            help=(
                "Mark quotations mentioning these words, comma separated. Nothing is "
                "removed - a quotation can be about a subject without naming it."
            ),
        ),
    ] = None,
) -> None:
    """Assemble collected corpora into one file, re-checking every quotation as it goes.

    No model is involved. Each quotation is looked for again in the document it names, so a
    corpus written by older code tells the truth without being re-generated: before v1.2.0
    the writer labelled an unplaceable quotation a fabrication, which is the error ADR-042
    exists to correct.

    Quotations are grouped by outcome, because a reader wants the ones they can cite first
    and the ones they must not cite marked as such.
    """
    _, workspace = _load(config_path)
    collected: list[CollectedClaim] = []
    for source in sources:
        try:
            text = workspace.resolve_within(source).read_text(encoding="utf-8", errors="replace")
        except (ValueError, OSError) as error:
            console.print(f"[red]Cannot read {source}: {error}[/red]")
            raise typer.Exit(code=1) from error
        collected.extend(parse_corpus(text))

    if not collected:
        console.print("[yellow]Nothing to assemble.[/yellow] Those files hold no quotations.")
        raise typer.Exit(code=1)

    marked = about(tuple(collected), _words(about_words))
    rechecked, missing = recheck(collected, workspace)
    text = assembled(rechecked, marked, sources)

    try:
        write_new_file(workspace.resolve_within(into), text)
    except ConversionError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    real = sum(1 for _, found in rechecked if found)
    console.print(f"[green]{len(collected)} quotations from {len(sources)} files[/green] -> {into}")
    console.print(f"  {real} are in their document, {len(collected) - real} are not.")
    if marked:
        shown = sum(1 for claim, _ in rechecked if claim.quote in marked)
        console.print(f"  {shown} mention your words; none were removed.")
    if missing:
        console.print(
            f"[yellow]{len(missing)} came from documents not in the workspace[/yellow] and "
            "could not be re-checked. They carry the label their corpus gave them."
        )


def _words(given: str | None) -> tuple[str, ...]:
    """Split a comma-separated option into words, dropping the empties."""
    return tuple(word.strip() for word in (given or "").split(",") if word.strip())


CANDIDATES_PER_PARAGRAPH = 3
"""How many quotations each paragraph is judged against.

Three, because the cost is one judgement each and a draft is dozens of paragraphs. More
candidates find more support and take proportionally longer; this is the number at which a
review of a section finishes while somebody is still willing to wait (ADR-068).
"""


@app.command()
def review(
    draft: Annotated[Path, typer.Argument(help="The document you wrote, in the workspace.")],
    against: Annotated[
        Path, typer.Option("--against", help="A corpus from `collect` or `corpus`.")
    ],
    into: Annotated[
        Path | None, typer.Option("--into", help="Write the report here as well.")
    ] = None,
    config_path: Annotated[
        Path, typer.Option("--config", "-c", help="Path to the configuration file.")
    ] = DEFAULT_CONFIG_PATH,
) -> None:
    """Read what **you** wrote against the sources **you** collected.

    Every other check here verifies text a model produced. This turns that around and asks,
    of each paragraph in your draft: is there anything in my own corpus that holds this up?

    **It reads and reports. It writes nothing and changes nothing** - revising is a separate
    act with a separate risk, and a tool that told you a sentence was unsupported and then
    rewrote it would just give you a fluent unsupported sentence.

    **Uncovered is not false.** A paragraph can be true and well argued while resting on a
    paper that is not in your corpus, which on a bibliography of two dozen papers is the
    ordinary case (ADR-068).
    """
    config, workspace = _load(config_path)
    try:
        written = workspace.resolve_within(draft)
        corpus_file = workspace.resolve_within(against)
    except ValueError as error:
        _show(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error
    for path, what in ((written, draft), (corpus_file, against)):
        if not path.exists():
            _show(f"[red]{what} is not in the workspace.[/red]")
            raise typer.Exit(code=1)

    blocks = paragraphs_in(written.read_text(encoding="utf-8", errors="replace"))
    if not blocks:
        _show("[yellow]Nothing in this document asserts anything.[/yellow]")
        raise typer.Exit(code=1)

    collected = [
        c
        for c in parse_corpus(corpus_file.read_text(encoding="utf-8", errors="replace"))
        if "NOT IN THE DOCUMENT" not in c.recorded_verdict
    ]
    if not collected:
        _show(f"[red]{against} holds no usable quotations.[/red]")
        raise typer.Exit(code=1)
    passages = tuple(
        Passage(text=c.quote, source=c.document, note=c.claim, page=c.page) for c in collected
    )
    retriever = _retriever_for(config, corpus_file)

    judgements = len(blocks) * CANDIDATES_PER_PARAGRAPH
    _show(
        f"[bold]{len(blocks)} paragraphs[/bold] against [bold]{len(passages)} quotations[/bold]: "
        f"about {judgements} judgements, a few seconds each."
    )
    if not typer.confirm("Read it?", default=True):
        raise typer.Exit(code=1)

    provider = _build_provider(ProviderChoice.ollama, config)
    judge = AskingJudge(provider)
    findings: list[Finding] = []
    # A budget large enough for everything: the ranking is what is wanted here, not a
    # selection, and a quotation dropped for space would be support the writer never sees.
    # Computed once - the corpus does not change between paragraphs.
    whole = sum(estimate_tokens(passage.text) for passage in passages) + len(passages)
    with console.status(f"Reading {len(blocks)} paragraphs..."):
        for block in blocks:
            nearest = retriever.select(block.text, passages, whole).chosen
            judged = [
                (p.source, p.text, judge.judge(block.text, p.text))
                for p in nearest[:CANDIDATES_PER_PARAGRAPH]
            ]
            findings.append(concluded(block, judged))

    against_it = [f for f in findings if f.verdict == "contradicted"]
    uncovered = [f for f in findings if f.verdict == "nothing"]
    held = len(findings) - len(against_it) - len(uncovered)
    if against_it:
        _show(f"[red]{len(against_it)} paragraphs your corpus contradicts.[/red] Read these first.")
        for finding in against_it:
            _show(f"  [red]Line {finding.paragraph.line}[/red] - {finding.document}")
    _show(f"[green]{held} held up[/green], [yellow]{len(uncovered)} not covered[/yellow].")
    _show(
        "[dim]Not covered means nothing collected holds it - not that it is wrong. The "
        "source may simply not be in this corpus.[/dim]"
    )
    written_report = report(findings, draft.name, against.name, 0)
    if into:
        destination = workspace.resolve_within(into)
        _write_or_exit(destination, written_report)
        # The same findings as data, beside the report, so the window can paint them over
        # the draft without re-running an engine (ADR-069).
        reviewed = Reviewed(draft=draft.name, corpus=against.name, findings=tuple(findings))
        write_new_file(
            destination.with_suffix(FINDINGS_SUFFIX),
            reviewed.model_dump_json(indent=2),
        )
        _show(f"-> {into}")


def _engine_seen(config: Config) -> EngineSeen:
    """Ask the engine whether it answers, as the window's contract rather than the adapter's.

    Composition: the window is handed this to call, so a view never touches an adapter and
    nothing is asked until somebody presses the button (ADR-077).
    """
    host = resolve_engine_host(config.engine_host, config.network_access)
    if not config.model:
        return EngineSeen(asked=True, detail="No model is configured.")
    found = check_engine(config.model, host, config.context_tokens)
    return EngineSeen(
        asked=True,
        reached=found.reached,
        answered=found.answered,
        models=len(found.models),
        seconds=found.seconds or 0.0,
        detail=found.detail,
    )


def _asking_for_the_window(
    config: Config, workspace: Workspace
) -> tuple[Callable[..., Prepared], Callable[[Prepared], Asked]]:
    """Compose the one action the window may run (ADR-085).

    Composition, which is the driving adapter's job (ADR-029), and why this sits in a view
    although it draws nothing. A slice may reach only `core` and `ports`, and a section only
    those plus `features/` - so neither can build a provider, open an audit log or call the
    cycle. The window is handed the ability to run one thing and cannot obtain it for itself.
    """
    skill = AskCorpusSkill()

    def prepare_one(question: str, corpus: str, carried: tuple[Passage, ...] = ()) -> Prepared:
        """Rank a corpus against a question. The prompt is not sent.

        ``carried`` is what a thread has already established, and goes in front of what the
        ranking chooses - never the model's own prose, which re-entering a prompt is how an
        invention would come to verify (ADR-091).
        """
        try:
            path = workspace.resolve_within(Path(corpus))
            text = path.read_text(encoding="utf-8", errors="replace")
        except (ValueError, OSError) as error:
            return Prepared(question=question.strip(), corpus=corpus, refusal=str(error))
        return prepare(question, corpus, text, config, _retriever_for(config, path), carried)

    def send_one(prepared: Prepared) -> Asked:
        """Send a question that was previewed. **This never raises**, by contract.

        It runs on a worker thread, and an exception crossing a thread boundary into Tk is a
        window that stops repainting with nothing on the screen to say why. Every way this
        can fail becomes a sentence the section draws where an answer would go.
        """
        try:
            provider = _build_provider(ProviderChoice.ollama, config, skill.name)
            plan = skill.plan((prepared.question,), config)
            return answer_prepared(
                prepared,
                skill,
                plan,
                config,
                workspace,
                provider,
                AuditLog(workspace, config),
                new_run_id(),
            )
        except Exception as error:  # noqa: BLE001 - see the docstring; nothing may escape
            return Asked(prepared=prepared, failure=str(error))

    return prepare_one, send_one


@app.command()
def window(
    config_path: Annotated[
        Path, typer.Option("--config", "-c", help="Path to the configuration file.")
    ] = DEFAULT_CONFIG_PATH,
) -> None:
    """Open a window on the work in your workspace, and ask it one kind of question.

    **Eight sections read; one asks.** No skill is run from here and nothing is written - the
    single action available is a question against a corpus that is already there, behind a
    preview that has to be drawn before the control that sends it exists (ADR-085). A review
    is still produced by `lacc review --into`; this opens the findings and paints them over
    the draft (ADR-069).

    Needs the optional toolkit: `pip install local-ai-control-center[gui]`.
    """
    config, workspace = _load(config_path)
    try:
        from local_ai_control_center.window import show
    except ImportError:  # noqa: F401 - the toolkit is optional by design
        # The brackets are escaped because Rich reads `[gui]` as markup and prints
        # nothing at all - which turned this very message into instructions that left
        # out the one part that matters.
        _show(
            "[red]The window needs CustomTkinter.[/red] Install it with "
            r"`pip install local-ai-control-center\[gui]`, or with uv: "
            r"`uv sync --extra gui` and run it as `uv run --extra gui lacc window`. "
            "Everything else works without it."
        )
        raise typer.Exit(code=1) from None
    # Hidden, in the workspace: the window's own preferences are not the user's documents
    # and should not appear among them, and they are not configuration either (ADR-069).
    saved = workspace.root / WINDOW_PREFERENCES
    preferences = preferences_from(saved)
    if not preferences.configuration:
        preferences = preferences.model_copy(update={"configuration": config_path.name})
    show(
        workspace.root,
        config_path.parent,
        preferences,
        saved,
        commands_of(app),
        prompts_of(_known_skills(config_path), config),
        status_of(workspace.root, config),
        lambda: _engine_seen(config),
        *_asking_for_the_window(config, workspace),
        config.context_file or "",
    )


@app.command()
def coverage(
    topics_file: Annotated[
        Path, typer.Argument(help="One topic per line. Mark the control with `!`.")
    ],
    against: Annotated[
        Path, typer.Option("--against", help="A corpus written by lacc collect or lacc corpus.")
    ],
    into: Annotated[Path | None, typer.Option("--into", help="Where to write the report.")] = None,
    config_path: Annotated[
        Path, typer.Option("--config", "-c", help="Path to the configuration file.")
    ] = DEFAULT_CONFIG_PATH,
) -> None:
    """How far the nearest quotation is from each topic you name.

    **It says what is thin. It cannot say what is missing** - LACC knows nothing of your field
    beyond the documents you brought, and naming an absent subject would be a model's memory
    rather than your sources.

    **Nothing is called a gap.** A similarity has no meaning on its own, so one line of your
    topics file must be marked with `!` as a subject deliberately *outside* your field. That
    is the floor the rest are read against, and without it the numbers are unanchored
    (ADR-088).

    Needs `embedding_model`. Shared words were measured for this and produce a report that
    looks the same and is wrong: they called a topic absent that the corpus speaks to in other
    words, which is a false gap about your own bibliography.
    """
    config, workspace = _load(config_path)
    if not config.embedding_model:
        _show(
            "[red]This needs an embedding model.[/red] Set `embedding_model: bge-m3` in your "
            "configuration. Word overlap was measured for this job and reported a topic as "
            "absent that the corpus covers in other words - a false gap is the one thing a "
            "coverage report must not produce (ADR-088)."
        )
        raise typer.Exit(code=1)
    try:
        topics_path = workspace.resolve_within(topics_file)
        corpus_path = workspace.resolve_within(against)
        topics = topics_in(topics_path.read_text(encoding="utf-8", errors="replace"))
        text = corpus_path.read_text(encoding="utf-8", errors="replace")
    except (ValueError, OSError) as error:
        _show(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    if not topics:
        _show(f"[red]{topics_file} names no topics.[/red] One per line.")
        raise typer.Exit(code=1)
    if missing_control(topics):
        _show(
            f"[red]No control topic.[/red] Mark one line with `{CONTROL_MARK}` - a subject "
            "deliberately outside your field. Without a floor these numbers have no meaning, "
            "and a reader supplies one from somewhere."
        )
        raise typer.Exit(code=1)

    collected = [c for c in parse_corpus(text) if "NOT IN THE DOCUMENT" not in c.recorded_verdict]
    if not collected:
        _show(f"[yellow]{against} holds no quotation that was found in its document.[/yellow]")
        raise typer.Exit(code=1)
    passages = tuple(
        Passage(text=c.quote, source=c.document, note=c.claim, page=c.page) for c in collected
    )

    host = resolve_engine_host(config.engine_host, config.network_access)
    embedder = OllamaEmbedder(config.embedding_model, host)
    cache = corpus_path.with_suffix(corpus_path.suffix + VECTOR_SUFFIX)
    _show(
        f"[bold]{len(topics)} topics[/bold] against {len(passages)} quotations, by meaning. "
        f"[dim]{config.embedding_model} on {host}[/dim]"
    )
    try:
        vectors = tuple(DenseRetriever(embedder, cache).vectors_for(passages))
        found = reach_of(topics, passages, vectors, embedder)
    except (EmbeddingError, ValueError) as error:
        _show(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    floor = next((one.nearest for one in found if one.topic.control), 0.0)
    for one in found:
        name = f"{one.topic.said}  (control)" if one.topic.control else one.topic.said
        colour = "dim" if one.nearest <= floor else "white"
        _show(f"  [{colour}]{one.nearest:.2f}[/{colour}]  {name}")
    _show(
        f"[dim]The floor is {floor:.2f}. Nothing here is called a gap: a similarity is an "
        "ordering, not an interval.[/dim]"
    )

    if into is not None:
        taken = datetime.now(UTC).date().isoformat()
        destination = workspace.resolve_within(into)
        _write_or_exit(
            destination, coverage_report(found, against.name, config.embedding_model, taken)
        )
        # The numbers beside the report, the way findings sit beside a review: the window
        # paints a measurement without re-running an engine, and reads data rather than
        # parsing back the Markdown this just wrote (ADR-069).
        measured = Measured(
            corpus=against.name, model=config.embedding_model, taken=taken, reaches=found
        )
        beside = destination.with_suffix(REACHES_SUFFIX)
        beside.write_text(measured.model_dump_json(indent=2) + chr(10), encoding="utf-8")
        _show(f"[green]Written[/green] -> {into}")


@app.command()
def identify(
    document: Annotated[Path, typer.Argument(help="A document inside the workspace.")],
    doi: Annotated[
        str | None,
        typer.Option("--doi", help="The DOI this document is. Checked against the registry."),
    ] = None,
    config_path: Annotated[
        Path, typer.Option("--config", "-c", help="Path to the configuration file.")
    ] = DEFAULT_CONFIG_PATH,
) -> None:
    """Say which work a document is, when nothing in it says so.

    **Without `--doi` this chooses nothing.** It lists the DOIs the document prints near its
    front and asks the registry what each one is, so you can see which is the document itself
    and which are works it cites. That distinction is yours to make: measured over a real
    bibliography, **no test separated them** - a cited DOI scored 100% against the registry's
    own title, and at every narrower window a cited one outranked an owned one (ADR-087).

    With `--doi`, the registry is asked, the work it names is shown, and on confirmation the
    answer is written **beside** the document as `<document>.doi.json` - never into it, because
    the corpus checks hundreds of quotations against these files as they are. `lacc resolve`
    reads it afterwards for any document whose own metadata is silent.
    """
    config, workspace = _load(config_path)
    if not config.registry_url or not config.network_access:
        _show(
            "[red]This asks a registry, so it needs both switches on.[/red] Write "
            "`registry_url: https://api.crossref.org` and `network_access: true` in your "
            "configuration. Both are off by default."
        )
        raise typer.Exit(code=1)
    try:
        path = workspace.resolve_within(document)
    except ValueError as error:
        _show(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error
    if not path.exists():
        _show(f"[red]{document} is not in the workspace.[/red]")
        raise typer.Exit(code=1)

    registry = RememberedRegistry(
        CrossrefRegistry(config.registry_url, config.registry_mailto),
        workspace.resolve_within(Path("identified.registry.json")),
    )
    already = established_for(path)
    if already is not None:
        _show(f"[dim]Already established as {already.doi} on {already.established}.[/dim]")

    if doi is None:
        _propose(path, registry, config)
        return

    wanted = doi.strip()
    _show(f"[yellow]1 DOI would be sent to {config.registry_url}.[/yellow]")
    if not typer.confirm("Ask the registry?", default=False):
        _show("Nothing was sent.")
        raise typer.Exit(code=1)
    try:
        work = registry.about(wanted)
    except RegistryError as error:
        _show(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error
    registry.write()
    if work is None:
        _show(f"[red]The registry holds nothing for {wanted}.[/red] Nothing was written.")
        raise typer.Exit(code=1)

    _show(f"[bold]{work.title}[/bold]")
    _show(f"[dim]{as_entry(work)}[/dim]")
    said = opening_of(path.read_text(encoding="utf-8", errors="replace"))
    _show(f"[dim]The document opens: {said}[/dim]")
    if not typer.confirm("Is that what this document is?", default=False):
        _show("[yellow]Nothing was written.[/yellow] A wrong DOI is worse than a missing one.")
        raise typer.Exit(code=1)
    written = establish(path, wanted, work.title)
    _show(f"[green]Established[/green] -> {written.name}")


def _propose(path: Path, registry: RememberedRegistry, config: Config) -> None:
    """List the DOIs a document prints, with what the registry says each one is."""
    candidates = printed_dois(path.read_text(encoding="utf-8", errors="replace"))
    if not candidates:
        _show(
            f"[yellow]{path.name} prints no DOI in its front matter.[/yellow] Nothing to "
            "propose - two of the four documents this was measured on are arXiv preprints, "
            "which carry none."
        )
        return
    fresh = [one for one in candidates if not registry.holds(one)]
    _show(f"[bold]{len(candidates)} DOIs[/bold] printed near the front of {path.name}.")
    if fresh:
        _show(f"[yellow]{len(fresh)} would be sent to {config.registry_url}.[/yellow]")
        if not typer.confirm("Ask the registry what they are?", default=False):
            _show("Nothing was sent.")
            return
    for one in candidates:
        try:
            work = registry.about(one)
        except RegistryError as error:
            _show(f"  [red]{one}[/red]  {error}")
            continue
        if work is None:
            _show(f"  [dim]{one}[/dim]  the registry holds nothing for it")
            continue
        _show(f"  [bold]{one}[/bold]  {work.title}")
    registry.write()
    said = opening_of(path.read_text(encoding="utf-8", errors="replace"))
    _show(f"[dim]The document opens: {said}[/dim]")
    _show(
        "[dim]Nothing was chosen. A document prints its own DOI and the DOIs it cites, and "
        "no test separates them - which is why this asks you. Name one with --doi.[/dim]"
    )


@app.command()
def sections(
    source: Annotated[Path, typer.Argument(help="A document inside the workspace.")],
    about: Annotated[
        str | None,
        typer.Option("--about", help="Order them by what a question is about."),
    ] = None,
    take: Annotated[
        str | None, typer.Option("--take", help="Write one section out, by its number.")
    ] = None,
    into: Annotated[Path | None, typer.Option("--into", help="Where to write it.")] = None,
    config_path: Annotated[
        Path, typer.Option("--config", "-c", help="Path to the configuration file.")
    ] = DEFAULT_CONFIG_PATH,
) -> None:
    """List the sections a document numbers for itself, and take one out.

    **Read from the document's own numbering, never guessed from how a line looks.** A PDF
    does not say what a heading is, so what is found here is what the author numbered: a dot
    after the number, a short title, no page number trailing it, and first-level numbers that
    run 1, 2, 3 without gaps.

    Fourteen of twenty-four documents in a real bibliography number nothing, and that is
    reported rather than worked around. **Nothing is written into the document** - the
    quotations already checked against it stay checked (ADR-076).
    """
    config, workspace = _load(config_path)
    try:
        path = workspace.resolve_within(source)
    except ValueError as error:
        _show(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error
    if not path.exists():
        _show(f"[red]{source} is not in the workspace.[/red]")
        raise typer.Exit(code=1)

    text = path.read_text(encoding="utf-8", errors="replace")
    found = sections_in(text)
    if not found:
        _show(
            f"[yellow]{source.name} numbers no sections.[/yellow] Most do not: a heading in a "
            "PDF is a larger font, and nothing of that survives extraction. Read it in passes "
            "instead, with `--in-passes`."
        )
        raise typer.Exit(code=1)

    if take is None:
        if about:
            # Ranked, and **all** of them: which to read is the reader's decision, and a
            # list that showed only the top would be making it for them (ADR-079).
            found = ranked(text, about, _retriever_for(config, None))
            _show(f"[bold]{len(found)} sections[/bold] in {source.name}, most about it first")
            for section in found[:12]:
                _show(f"  [dim]{section.line:>6}[/dim]  {section.number}  {section.title}")
            if len(found) > 12:
                _show(f"  [dim]and {len(found) - 12} more, in the same order[/dim]")
            _show("[dim]Nothing was read but this document. Take one with --take.[/dim]")
            return
        _show(f"[bold]{len(found)} sections[/bold] in {source.name}")
        for section in found:
            indent = "  " * (section.depth - 1)
            _show(f"  [dim]{section.line:>6}[/dim]  {indent}{section.number}  {section.title}")
        _show("[dim]Order them by a question with --about, or take one with --take.[/dim]")
        return

    wanted = section_of(text, take)
    if not wanted:
        _show(f"[red]{source.name} does not number a section {take}.[/red]")
        raise typer.Exit(code=1)
    if into is None:
        _show("[red]Name where to write it with --into.[/red]")
        raise typer.Exit(code=1)
    destination = workspace.resolve_within(into)
    _write_or_exit(destination, wanted)
    # Which document this came out of, beside the file rather than inside it. Nothing is
    # written into an extract: the quotations checked against these files stay checked
    # (ADR-076), and this is a fact about the file (ADR-082).
    write_new_file(
        destination.with_suffix(destination.suffix + TAKEN_FROM),
        json.dumps(
            {
                "document": source.name,
                "section": take,
                "taken_on": datetime.now(UTC).strftime("%Y-%m-%d"),
            },
            indent=2,
        ),
    )
    _show(
        f"[green]Section {take}[/green] -> {into}   "
        f"[dim]{estimate_tokens(wanted):,} tokens of {estimate_tokens(text):,}[/dim]"
    )


@app.command()
def status(
    config_path: Annotated[
        Path, typer.Option("--config", "-c", help="Path to the configuration file.")
    ] = DEFAULT_CONFIG_PATH,
) -> None:
    """Where the work stands, stage by stage, and what each stage is missing.

    **Counted from the files, now.** No model is called, nothing is written and nothing
    leaves. Every figure here can be re-taken in seconds, which is why none of it is stored:
    a number written down is one that will be true for a while and then quietly stop being.

    A stage reports what is **missing** as well as what is done. "832 quotations" reads like
    success; "832 quotations, 2 documents with none" is the same fact with the part that
    still needs doing attached (ADR-080).
    """
    config, workspace = _load(config_path)
    work = stages_in(workspace.root, config.context_file)
    if not work.stages:
        _show(f"[red]{workspace.root} is not a folder.[/red]")
        raise typer.Exit(code=1)

    _show(f"[dim]{work.workspace}[/dim]")
    for stage in work.stages:
        mark = "[green]done[/green]" if stage.settled else "[yellow]open[/yellow]"
        _show("")
        _show(f"  {mark}  [bold]{stage.name}[/bold]")
        if stage.done:
            _show(f"        {stage.done}")
        if stage.missing:
            _show(f"        [yellow]{stage.missing}[/yellow]")
        if not stage.done:
            _show(f"        [dim]{stage.command}[/dim]")
    _show("")
    _show(f"[dim]{work.settled} of {len(work.stages)} stages have nothing outstanding.[/dim]")


@app.command()
def verify(
    config_path: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to the configuration file."),
    ] = DEFAULT_CONFIG_PATH,
) -> None:
    """Check that the audit trail has not been altered since it was written."""
    _, workspace = _load(config_path)
    audit = AuditLog(workspace, load_config(config_path))
    result = verify_chain(audit.path)

    if result.unreadable_at is not None:
        console.print(
            f"[red]The trail cannot be read[/red] at record {result.unreadable_at} ({audit.path})."
        )
        raise typer.Exit(code=1)

    if not result.intact:
        console.print(
            f"[red]The trail has been altered.[/red] The chain first breaks at record "
            f"{result.broken_at} of {result.records} in {audit.path}. Every record from "
            "there on is no longer vouched for by the ones before it."
        )
        raise typer.Exit(code=1)

    console.print(
        f"[green]The trail holds.[/green] {result.records} records in {audit.path}, "
        "each linked to the one before it."
    )
    if result.first_seen:
        console.print(f"From {result.first_seen} to {result.last_seen}.")
    if result.unverifiable:
        console.print(
            f"[yellow]{result.unverifiable} of them predate the chain[/yellow] and cannot "
            "be vouched for either way."
        )
    _report_the_anchor(check_anchor(audit.path))
    # Two limits, and the one that was never stated is the easier attack. Tested: editing,
    # deleting a middle record and reordering are all caught; removing records from the end
    # is not, and no chain can catch it from the file alone (ADR-043).
    console.print(
        "[dim]The chain catches a record edited, removed from the middle, or reordered. It "
        "does not catch records removed from the end - a shorter chain is still a valid "
        "chain - nor a deliberate rewrite, since whatever can write the file can recompute "
        "the digests. The anchor beside the trail catches loss, and sits under the same "
        "permissions as the trail, so it does not catch a person who wants it gone. If you "
        "keep your notifications, those are the only record of this that is not on this "
        "machine.[/dim]"
    )


def _report_the_anchor(anchor: AnchorCheck) -> None:
    """Say what the sidecar beside the trail knows, and what it cannot know.

    Three outcomes rather than two: shorter than it was, and a changed last record, are
    different events with different causes (ADR-049).
    """
    if not anchor.present:
        console.print(
            "[dim]This trail has no anchor beside it - it was written before anchors "
            "existed. One will be written the next time something is recorded.[/dim]"
        )
        return
    if anchor.agrees:
        console.print(
            f"[green]The anchor agrees:[/green] {anchor.expected_records} records, and the "
            "last one is the last one it saw."
        )
        return
    if anchor.lost:
        console.print(
            f"[red]{anchor.lost} records are missing from the end.[/red] The anchor "
            f"remembers {anchor.expected_records} and the trail holds {anchor.found_records}. "
            "A crashed write, a synchronisation conflict or a restored backup will do this; "
            "so will somebody removing them."
        )
        return
    if anchor.head_changed:
        console.print(
            "[red]The last record is not the one the anchor saw.[/red] The count matches, so "
            "nothing was removed - the final record was replaced."
        )
        return
    console.print(
        f"[yellow]The trail is longer than the anchor remembers[/yellow] "
        f"({anchor.found_records} against {anchor.expected_records}). Something wrote to it "
        "without going through LACC."
    )


@app.command()
def profile() -> None:
    """Detect and report what this machine offers, without changing anything."""
    result = profile_system()
    _show_profile(result)


def _show_profile(profile: SystemProfile) -> None:
    """Render a system profile with Rich."""
    if profile.engine_present:
        if profile.installed_models:
            lines = [
                f"- {model.name}  ({model.size_gb} GB, {model.quantization}"
                + (
                    f", up to {model.context_tokens:,} tokens)"
                    if model.context_tokens
                    else ", window unknown)"
                )
                for model in profile.installed_models
            ]
            models_text = "\n".join(lines)
        else:
            models_text = "Engine present, but no models installed."
    else:
        models_text = "No local engine detected."
    console.print(Panel(models_text, title="Inference engine", expand=False))

    hardware_lines = [
        f"OS:           {profile.os_name}",
        f"Architecture: {profile.architecture}",
    ]
    if profile.processor:
        hardware_lines.append(f"Processor:    {profile.processor}")
    hardware_lines.extend(
        [
            f"CPU count:    {profile.cpu_count}",
            f"Total memory: {profile.total_memory_gb} GB",
            f"Free disk:    {profile.free_disk_gb} GB",
            f"Uptime:       {profile.uptime_hours} h",
        ]
    )
    console.print(Panel("\n".join(hardware_lines), title="Hardware", expand=False))

    table = Table(title="Rough model fit (approximate)", expand=False)
    table.add_column("Size")
    for bits in (3, 4, 8):
        table.add_column(f"{bits}-bit", justify="right")

    by_size: dict[int, dict[int, str]] = {}
    for fit in profile.fits:
        cell = f"{fit.weight_gb} GB"
        if fit.status == "too_large":
            cell = f"[red]{cell}[/red]"
        elif fit.status == "tight":
            cell = f"[yellow]{cell}[/yellow]"
        else:
            cell = f"[green]{cell}[/green]"
        by_size.setdefault(fit.parameters_b, {})[fit.quantization_bits] = cell

    for size in sorted(by_size):
        row = [f"{size}B"] + [by_size[size].get(bits, "") for bits in (3, 4, 8)]
        table.add_row(*row)

    console.print(table)

    _show_window_costs(profile)

    for note in profile.notes:
        console.print(f"[yellow]note:[/yellow] {note}")


def _show_window_costs(profile: SystemProfile) -> None:
    """Render what each context window size would cost, with what it assumes.

    A range rather than a recommendation (ADR-021). A single suggested number would be
    easier to read and would hide the assumptions that produced it, which is how a value
    chosen for one machine ends up in someone else's configuration.
    """
    if not profile.window_costs:
        return

    free = profile.available_memory_gb
    table = Table(
        title=f"What a context window costs (approximate, {free} GB free now)",
        expand=False,
    )
    table.add_column("Model")
    table.add_column("context_tokens", justify="right")
    table.add_column("Cache", justify="right")
    table.add_column("Total with weights", justify="right")

    colours = {"too_large": "red", "tight": "yellow", "fits": "green"}
    for cost in profile.window_costs:
        colour = colours[cost.status]
        table.add_row(
            cost.model,
            f"{cost.window_tokens:,}",
            f"{cost.cache_gb} GB",
            f"[{colour}]{cost.total_gb} GB[/{colour}]",
        )
    console.print(table)
    console.print(
        "[dim]Assumes a 16-bit cache, the whole model in RAM, and ordinary attention; "
        "free memory is a snapshot and moves. LACC does not set `context_tokens` for "
        "you - copy the size you want into your configuration.[/dim]"
    )


def _report(result: RunResult) -> None:
    """Print the outcome of a run."""
    if result.outcome == "completed" and result.completion is not None:
        try:
            console.print(Panel(result.completion.text, title="Result", expand=False))
        except (UnicodeEncodeError, OSError):
            _show(result.completion.text)
    elif result.outcome == "refused":
        _exit_refused()
    elif result.outcome == "declined":
        console.print("[yellow]Declined.[/yellow] Nothing was run.")


def _exit_refused() -> None:
    """Report a refusal and exit 1.

    A refused run exits non-zero so that a script checking the exit code is not told the
    work succeeded when nothing ran (ADR-017). A declined run keeps exiting 0: nothing
    failed there - the human was asked and said no, which is the system working.
    """
    console.print("[red]Refused:[/red] the action would not be allowed.")
    raise typer.Exit(code=1)


engine_app = typer.Typer(help="Check the engine LACC will actually use.", no_args_is_help=True)
app.add_typer(engine_app, name="engine")


@engine_app.command("test")
def engine_test(
    config_path: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to the configuration file."),
    ] = DEFAULT_CONFIG_PATH,
) -> None:
    """Ask the engine the questions a run is about to assume the answers to.

    `lacc profile` reports the *local* engine, because the address it uses refuses anything
    that is not loopback by design. That makes it the wrong thing to check when the engine
    is a machine of your own on a private network - which is what error messages used to
    send people to. This checks the host the configuration actually names.

    Exits non-zero when a run would not get an answer, so it is usable from a script.
    """
    config, _ = _load(config_path)
    host = resolve_engine_host(config.engine_host, config.network_access)
    console.print(f"Engine: [bold]{host}[/bold]  model: [bold]{config.model or '(none)'}[/bold]")

    if not config.model:
        console.print("[red]No model configured.[/red] Name one with `model:` in the config.")
        raise typer.Exit(code=1)

    check = check_engine(config.model, host, config.context_tokens)
    if not check.reached:
        console.print(f"[red]{check.detail}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[green]Reached it.[/green] {len(check.models)} models installed.")
    if not check.model_installed:
        console.print(f"[red]{check.detail}[/red]")
        if check.models:
            console.print("Installed there: " + ", ".join(check.models))
        raise typer.Exit(code=1)

    if not check.answered:
        console.print(f"[red]{check.detail}[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]It answered[/green] in {check.seconds}s. A run would work.")


notify_app = typer.Typer(help="Check and use the configured notifier.", no_args_is_help=True)
app.add_typer(notify_app, name="notify")


def _report_where_the_settings_came_from(config: Config, config_path: Path) -> None:
    """Say which named variables were found, by name only.

    Never their values: a token printed to a terminal is a token in the scrollback, in a
    screenshot, and in whatever the terminal logs to (ADR-030).
    """
    settings = config.notifier.ntfy
    found = [
        name
        for name in (settings.topic_env, settings.token_env)
        if os.environ.get(name, "").strip()
    ]
    if found:
        console.print(f"[dim]Found {', '.join(found)} in the environment.[/dim]")
    if settings.server_url:
        # The address, unlike the secrets, is safe to print: it is in the file already.
        console.print(f"[dim]Sending to {settings.server_url}, named in the configuration.[/dim]")


@notify_app.command("test")
def notify_test(
    config_path: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to the configuration file."),
    ] = DEFAULT_CONFIG_PATH,
) -> None:
    """Send one test notification, so settings are checked before being relied on.

    Exits non-zero when nothing was delivered, so the check is usable from a script.
    """
    config, workspace = _load(config_path)
    audit = AuditLog(workspace, config)
    run_id = new_run_id()
    _report_where_the_settings_came_from(config, config_path)

    try:
        notifier = notifier_from_config(config)
    except NotifierMisconfigured as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    if notifier is None:
        settings = config.notifier.ntfy
        console.print(
            "[yellow]No notifier configured.[/yellow] Notifications need `network_access: true`, "
            "`notifier.ntfy.enabled: true`, a `server_url`, and the named variables set."
        )
        if not settings.server_url:
            console.print(
                "No [bold]server_url[/bold] in the configuration. The address is a destination "
                "and is written there, not in the environment."
            )
        if not os.environ.get(settings.topic_env, "").strip():
            console.print(
                f"Nothing found for: {settings.topic_env}. Put it in "
                f"[bold]{config_path.parent / DOTENV_FILENAME}[/bold] or in your environment."
            )
        raise typer.Exit(code=1)

    delivery = notifier.send(
        Notification(
            title="LACC: notifier test",
            body="If this arrived, notifications are configured.",
            tags=("bell",),
        )
    )
    audit.record(
        run_id,
        "notification_sent" if delivery.delivered else "notification_failed",
        f"Test notification via {delivery.transport}: {delivery.detail}",
        {"transport": delivery.transport, "delivered": delivery.delivered},
    )
    if not delivery.delivered:
        console.print(f"[red]Not delivered[/red] ({delivery.transport}): {delivery.detail}")
        raise typer.Exit(code=1)
    console.print(f"[green]Sent[/green] via {delivery.transport}: {delivery.detail}")


def main() -> None:
    """Entry point for the `lacc` console script."""
    app()
