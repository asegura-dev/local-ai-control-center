"""Command-line interface: the `lacc` command.

The first human interface to the system (ADR-010). Built with Typer and rendered
with Rich, both confined here so the core stays free of interface code. `run` plans
a skill, previews it, asks for confirmation (defaulting to no), and executes;
`preview` shows what would happen without doing it.
"""

from __future__ import annotations

import os
import time
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from local_ai_control_center.audit import AuditLog, verify_chain
from local_ai_control_center.config import (
    DOTENV_FILENAME,
    Config,
    load_config,
    load_dotenv,
)
from local_ai_control_center.converter import ConversionError, converter_for
from local_ai_control_center.cycle import (
    WINDOW_TOLERANCE,
    PromptTooLargeError,
    ReadError,
    RunResult,
    answer_reserve,
    run_conversion,
)
from local_ai_control_center.notifier import (
    Notification,
    NotifierMisconfigured,
    notifier_from_config,
)
from local_ai_control_center.permissions import grant
from local_ai_control_center.preview import ExecutionPreview, IntendedAction, preview_action
from local_ai_control_center.profiler import SystemProfile, profile_system
from local_ai_control_center.provider import (
    MockProvider,
    OllamaProvider,
    Provider,
    ProviderError,
    resolve_engine_host,
)
from local_ai_control_center.run import new_run_id
from local_ai_control_center.skill import (
    CritiqueFileSkill,
    ExtractClaimsSkill,
    ReviseFileSkill,
    Skill,
    SkillPlan,
    SummarizeFileSkill,
    grant_for,
    run_skill,
)
from local_ai_control_center.workspace import (
    Workspace,
    WorkspaceExposed,
    sync_folder_suspicion,
    workspace_from_config,
)

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


def _resolve_skill(name: str) -> Skill:
    """Look up a skill by name, or exit with the list of known skills."""
    skill = _SKILLS.get(name)
    if skill is None:
        available = ", ".join(sorted(_SKILLS)) or "(none)"
        console.print(f"[red]Unknown skill:[/red] {name}")
        console.print(f"Available skills: {available}")
        raise typer.Exit(code=1)
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
) -> None:
    """Plan a skill, preview it, confirm, then execute and record it."""
    resolved = _resolve_skill(skill)
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
    if not _confirm(preview):
        console.print("[yellow]Declined.[/yellow] Nothing was run.")
        return

    run_id = new_run_id()
    generating = provider_choice is ProviderChoice.ollama
    started = time.monotonic()
    try:
        if generating:
            with console.status("Contacting Ollama...") as status:
                status.update(
                    "Generating... (the first run loads the model into memory and may take longer)"
                )
                result = _do_run(
                    resolved, tuple(requests), config, workspace, provider, audit, run_id
                )
        else:
            result = _do_run(resolved, tuple(requests), config, workspace, provider, audit, run_id)
    except (ProviderError, ReadError, PromptTooLargeError) as error:
        _announce(resolved.name, "failed", time.monotonic() - started, config, audit, run_id)
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    _announce(resolved.name, result.outcome, time.monotonic() - started, config, audit, run_id)
    _report(result)
    _show_checked_quotations(result)
    _warn_about_the_answer(result, config)
    if config.context_tokens is None:
        _warn_no_context_ceiling()


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

    unverified = sum(1 for checked in result.checked_claims if not checked.holds)
    if unverified:
        console.print(
            f"[red]{unverified} of {len(result.checked_claims)} quotations did not check "
            "out.[/red] Do not cite those without opening the document yourself."
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


def _do_run(
    resolved: Skill,
    requests: tuple[str, ...],
    config: Config,
    workspace: Workspace,
    provider: Provider,
    audit: AuditLog,
    run_id: str,
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
    )


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

    notification = Notification(
        title=f"LACC: {skill_name} {outcome}",
        body=f"{skill_name} {outcome} after {elapsed:.0f}s",
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
    resolved = _resolve_skill(skill)
    config, workspace = _load(config_path)
    plan = _plan_or_exit(resolved, tuple(requests), config)
    result = preview_action(
        plan.action, grant_for(resolved, config), config, workspace, config.remote_engine
    )
    _show_preview(result)


@app.command()
def ingest(
    source: Annotated[
        Path,
        typer.Argument(help="Document to convert (PDF or .docx), inside the workspace."),
    ],
    destination: Annotated[
        Path | None,
        typer.Argument(help="Where to write the text. Defaults to the source with a .md suffix."),
    ] = None,
    config_path: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to the configuration file."),
    ] = DEFAULT_CONFIG_PATH,
) -> None:
    """Extract a document's text into a file LACC can read, after preview and confirmation."""
    config, workspace = _load(config_path)
    audit = AuditLog(workspace, config)
    target = destination if destination is not None else source.with_suffix(".md")

    try:
        converter = converter_for(source)
    except ConversionError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    action = IntendedAction(
        name="ingest",
        summary=f"Extract the text of {source} into {target}",
        required=frozenset({"read_files", "write_files"}),
        targets=(source,),
        writes=(target,),
    )

    try:
        result = run_conversion(
            action,
            source,
            target,
            converter,
            grant(action.required, config),
            config,
            workspace,
            audit,
            new_run_id(),
            _confirm,
        )
    except ConversionError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    _report_ingestion(result, target, getattr(converter, "furniture_dropped", 0))


def _report_ingestion(result: RunResult, destination: Path, furniture: int = 0) -> None:
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
    resolved = _resolve_skill(skill)
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
            rows.append((attempt, len(checked), sum(1 for c in checked if c.holds)))

    _report_the_spread(resolved.name, config.model, rows)


def _report_the_spread(skill_name: str, model: str, rows: list[tuple[int, int, int]]) -> None:
    """Show every run, then the range each column covered."""
    table = Table(title=f"{skill_name} against {model or 'the mock provider'}", expand=False)
    table.add_column("Run", justify="right")
    table.add_column("Quotations", justify="right")
    table.add_column("Verified", justify="right")
    table.add_column("Rate", justify="right")
    for attempt, total, held in rows:
        rate = f"{held * 100 // total}%" if total else "-"
        table.add_row(str(attempt), str(total), str(held), rate)
    console.print(table)

    totals = [total for _, total, _ in rows]
    verified = [held for _, _, held in rows]
    rates = [held * 100 // total for _, total, held in rows if total]
    console.print(f"  quotations  {_spread(totals)}")
    console.print(f"  verified    {_spread(verified)}")
    console.print(f"  rate        {_spread(rates)}")

    if rates and max(rates) - min(rates) >= 10:
        console.print()
        console.print(
            f"[yellow]This configuration varied by {max(rates) - min(rates)} points "
            f"across {len(rows)} runs.[/yellow] A single run would not have told you "
            "that, and cannot be compared against another single run."
        )


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
    if result.unverifiable:
        console.print(
            f"[yellow]{result.unverifiable} of them predate the chain[/yellow] and cannot "
            "be vouched for either way."
        )
    console.print(
        "[dim]This detects modification by anything that does not know the file is a "
        "chain. It does not detect a deliberate rewrite: whatever can write the file can "
        "recompute the digests.[/dim]"
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
