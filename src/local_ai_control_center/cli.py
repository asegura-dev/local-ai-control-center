"""Command-line interface: the `lacc` command.

The first human interface to the system (ADR-010). Built with Typer and rendered
with Rich, both confined here so the core stays free of interface code. `run` plans
a skill, previews it, asks for confirmation (defaulting to no), and executes;
`preview` shows what would happen without doing it.
"""

from __future__ import annotations

import os
import re
import time
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from local_ai_control_center.adapters.documents import (
    HiddenText,
    converter_for,
    embedded_metadata,
    embedded_outline,
)
from local_ai_control_center.adapters.mock import MockProvider
from local_ai_control_center.adapters.ntfy import notifier_from_config
from local_ai_control_center.adapters.ollama import (
    OllamaProvider,
    check_engine,
    resolve_engine_host,
)
from local_ai_control_center.core.budget import CHARS_PER_TOKEN, answer_reserve
from local_ai_control_center.core.config import DOTENV_FILENAME, Config, load_config, load_dotenv
from local_ai_control_center.core.corpus import CollectedClaim, about, parse_corpus
from local_ai_control_center.core.declared import (
    DeclarationError,
    FileSkill,
    load_declared_skills,
)
from local_ai_control_center.core.grounding import Claim, check_claim
from local_ai_control_center.core.headings import headings_in, matching
from local_ai_control_center.core.passes import PageRangeError
from local_ai_control_center.core.permissions import grant
from local_ai_control_center.core.preview import ExecutionPreview, IntendedAction, preview_action
from local_ai_control_center.core.run import Progress, ProgressFn, new_run_id
from local_ai_control_center.core.skill import (
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
    run_conversion,
    run_skill,
    write_new_file,
)
from local_ai_control_center.ports.converter import ConversionError, Converter
from local_ai_control_center.ports.notifier import Notification, NotifierMisconfigured
from local_ai_control_center.ports.provider import Provider, ProviderError
from local_ai_control_center.system.audit import (
    AnchorCheck,
    AuditLog,
    check_anchor,
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
console = Console()


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
            help="Read a document too large for the window in several passes over its pages.",
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
        provider = _build_provider(provider_choice, config)
    except ProviderError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    plan = _plan_or_exit(resolved, tuple(requests), config)
    preview = preview_action(
        plan.action, grant_for(resolved, config), config, workspace, config.remote_engine
    )
    _show_preview(preview)
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


def _build_provider(choice: ProviderChoice, config: Config) -> Provider:
    """Construct the chosen provider. Ollama needs a configured model; the mock does not."""
    if choice is ProviderChoice.mock:
        return MockProvider()
    host = resolve_engine_host(config.engine_host, config.network_access)
    return OllamaProvider(config.model, config.context_tokens, host)


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


def _spread(values: list[int]) -> str:
    """Describe a set of measurements by its range and middle, never by its average.

    A mean would reproduce the error this command exists to correct: it reports a single
    number for something whose whole finding is that a single number misleads (ADR-032).
    """
    if not values:
        return "-"
    ordered = sorted(values)
    median = ordered[len(ordered) // 2]
    if ordered[0] == ordered[-1]:
        return f"{ordered[0]}"
    return f"{ordered[0]} - {ordered[-1]}  (median {median})"


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
) -> None:
    """Run a skill several times and report the spread, not a single number.

    Measuring is a different act from running: it characterises a configuration rather than
    doing work, so it refuses any skill that writes and never varies the action between
    repetitions (ADR-032). One preview, one confirmation, covering all of them.
    """
    resolved = _resolve_skill(skill, config_path)
    if "write_files" in resolved.required:
        console.print(
            f"[red]{skill} writes files, and measuring must not act.[/red] Repeating an "
            "action that has effects would multiply them; a measurement only observes."
        )
        raise typer.Exit(code=1)

    config, workspace = _load(config_path)
    audit = AuditLog(workspace, config)
    try:
        provider = _build_provider(provider_choice, config)
    except ProviderError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    plan = _plan_or_exit(resolved, tuple(requests), config)
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
                result = _do_run(
                    resolved, tuple(requests), config, workspace, provider, audit, new_run_id()
                )
            except (ProviderError, ReadError, PromptTooLargeError) as error:
                where = "The warm-up run" if attempt == 0 else f"Run {attempt}"
                console.print(f"[red]{where} failed:[/red] {error}")
                raise typer.Exit(code=1) from error
            if attempt == 0:
                continue
            checked = result.checked_claims
            # Counted by whether the quotation is in the document. `holds` also requires a
            # page, which measures LACC's ability to place it rather than the model's
            # fidelity - and mixing the two is what made a corpus of real quotations look
            # like a third fabricated (ADR-042).
            rows.append((attempt, len(checked), sum(1 for c in checked if c.found)))

    _report_the_spread(resolved.name, config.model, rows)


def _report_the_spread(skill_name: str, model: str, rows: list[tuple[int, int, int]]) -> None:
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
    console.print(f"  quotations  {_spread(totals)}")
    console.print(f"  in the document  {_spread(verified)}")
    console.print(f"  rate        {_spread(rates)}")

    if rates and max(rates) - min(rates) >= 10:
        console.print()
        console.print(
            f"[yellow]This configuration varied by {max(rates) - min(rates)} points "
            f"across {len(rows)} runs.[/yellow] A single run would not have told you "
            "that, and cannot be compared against another single run."
        )


def _collected_markdown(
    skill_name: str, model: str, gathered: list[tuple[str, RunResult | str]]
) -> str:
    """Assemble the collected claims into a file meant to be worked from.

    The quotation comes before the claim in each block, because the quotation is what
    carries authority: the claim is the model's paraphrase, and a generated file invites
    being treated as a source when it is not (ADR-039).
    """
    lines = [
        f"# Claims collected by {skill_name}",
        "",
        f"From {len(gathered)} documents, using {model or 'the mock provider'}. Every "
        "quotation was checked against the document it came from; the page is the one LACC "
        "located, not the one the model gave.",
        "",
        "This file is generated. It is not a source: each claim is the model's paraphrase, "
        "and the quotation beneath it is what can be cited.",
        "",
    ]
    divided = [
        name for name, outcome in gathered if isinstance(outcome, RunResult) and outcome.passes > 1
    ]
    if divided:
        many = len(divided) > 1
        lines += [
            f"{len(divided)} of these {'were' if many else 'was'} too large for the window and "
            f"{'were' if many else 'was'} read in several passes over "
            f"{'their' if many else 'its'} pages. Every quotation was still checked against "
            "the whole document, but no reading held all of it, so anything said about such a "
            "document as a whole rests on less than it appears to.",
            "",
        ]
    for name, outcome in gathered:
        lines.append(f"## {name}")
        lines.append("")
        if isinstance(outcome, str):
            lines += [f"**Not collected.** {outcome}", ""]
            continue
        claims = outcome.checked_claims
        held = sum(1 for c in claims if c.found)
        how = (
            f" Read in {outcome.passes} passes, so the model never held all of it at once."
            if outcome.passes > 1
            else ""
        )
        unplaceable = sum(1 for c in claims if c.found and not c.holds)
        aside = f" {unplaceable} are in it with no page determinable." if unplaceable else ""
        lines += [
            f"*{held} of {len(claims)} quotations are in the document.*{aside}{how}",
            "",
        ]
        for checked in claims:
            # Three outcomes, not two. A quotation that is in the document and cannot be
            # placed on a page is not a fabrication, and calling it one is the error
            # ADR-042 exists to correct - which lived on here after the check was fixed.
            if checked.holds:
                page, mark = f"p. {checked.found_on_page}", "verified"
            elif checked.found:
                page, mark = "page unknown", "in the document, page not determined"
            else:
                page, mark = "page unknown", "**NOT IN THE DOCUMENT**"
            lines += [
                f"> {checked.claim.quote}",
                "",
                f"{page} - {mark}",
                "",
                checked.claim.claim,
                "",
            ]
            if checked.nearest:
                lines += [f"Closest text in the source: {checked.nearest}", ""]
    return chr(10).join(lines) + chr(10)


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
            help="Read documents too large for the window in several passes over their pages.",
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
        provider = _build_provider(provider_choice, config)
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
        write_new_file(destination, _collected_markdown(resolved.name, config.model, gathered))
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
    rechecked, missing = _recheck(collected, workspace)
    text = _assembled(rechecked, marked, sources)

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


def _recheck(
    collected: list[CollectedClaim], workspace: Workspace
) -> tuple[list[tuple[CollectedClaim, bool | None]], list[CollectedClaim]]:
    """Look for every quotation again in the document it names.

    Returns each claim with whether it is really there, or ``None`` when the document is no
    longer in the workspace - which is reported rather than guessed at.
    """
    sources: dict[str, str | None] = {}
    out: list[tuple[CollectedClaim, bool | None]] = []
    missing: list[CollectedClaim] = []
    for claim in collected:
        if claim.document not in sources:
            try:
                path = workspace.resolve_within(Path(claim.document))
                sources[claim.document] = path.read_text(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                sources[claim.document] = None
        text = sources[claim.document]
        if text is None:
            missing.append(claim)
            out.append((claim, None))
            continue
        out.append((claim, check_claim(Claim(claim=claim.claim, quote=claim.quote), text).found))
    return out, missing


_STANDINGS = ((True, "Citable"), (None, "Not re-checked"), (False, "Not in the document"))


def _assembled(
    rechecked: list[tuple[CollectedClaim, bool | None]],
    marked: frozenset[str],
    sources: list[Path],
) -> str:
    """Render one corpus, grouped by document, with each quotation's current standing."""
    named = ", ".join(source.name for source in sources)
    real = sum(1 for _, found in rechecked if found)
    lines = [
        "# Collected quotations",
        "",
        f"Assembled from {named}. Every quotation was looked for again in the document it "
        f"names: {real} of {len(rechecked)} are there.",
        "",
        "This file is generated and is not a source. The quotation is what can be cited; "
        "the line under it is the model's paraphrase and was never checked.",
        "",
    ]
    if marked:
        # Counted as entries rather than as distinct quotations: the same sentence can be
        # quoted from two documents, and the number here has to match what a reader counts.
        shown = sum(1 for claim, _ in rechecked if claim.quote in marked)
        lines += [
            f"**{shown} quotations are marked** with a bullet, for mentioning words you "
            "gave. Nothing was removed, and a quotation can be about a subject without "
            "naming it.",
            "",
        ]

    by_document: dict[str, list[tuple[CollectedClaim, bool | None]]] = {}
    for claim, found in rechecked:
        by_document.setdefault(claim.document, []).append((claim, found))

    for document, entries in by_document.items():
        here = sum(1 for _, found in entries if found)
        lines += [f"## {document}", "", f"*{here} of {len(entries)} are in the document.*", ""]
        for standing, heading in _STANDINGS:
            group = [c for c, found in entries if found is standing]
            if not group:
                continue
            lines += [f"### {heading}", ""]
            for claim in group:
                mark = "- " if claim.quote in marked else ""
                where = f"p. {claim.page}" if claim.page else "page unknown"
                lines += [f"{mark}> {claim.quote}", "", f"{where} - {claim.claim}", ""]
                if claim.nearest and standing is False:
                    lines += [f"Closest text in the source: {claim.nearest}", ""]
    return chr(10).join(lines) + chr(10)


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
        console.print(Panel(result.completion.text, title="Result", expand=False))
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
    named = (settings.server_url_env, settings.topic_env, settings.token_env)
    found = [name for name in named if os.environ.get(name, "").strip()]
    if found:
        console.print(f"[dim]Found {', '.join(found)} in the environment.[/dim]")


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
        missing = [
            name
            for name in (settings.server_url_env, settings.topic_env)
            if not os.environ.get(name, "").strip()
        ]
        console.print(
            "[yellow]No notifier configured.[/yellow] Notifications need `network_access: true`, "
            "`notifier.ntfy.enabled: true`, and the named variables set."
        )
        if missing:
            console.print(
                f"Nothing found for: {', '.join(missing)}. Put them in "
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
