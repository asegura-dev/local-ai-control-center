"""Command-line interface: the `lacc` command.

The first human interface to the system (ADR-010). Built with Typer and rendered
with Rich, both confined here so the core stays free of interface code. `run` plans
a skill, previews it, asks for confirmation (defaulting to no), and executes;
`preview` shows what would happen without doing it.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from local_ai_control_center.audit import AuditLog, verify_chain
from local_ai_control_center.config import Config, load_config
from local_ai_control_center.converter import ConversionError, converter_for
from local_ai_control_center.cycle import (
    WINDOW_TOLERANCE,
    PromptTooLargeError,
    ReadError,
    RunResult,
    answer_reserve,
    run_conversion,
)
from local_ai_control_center.permissions import grant
from local_ai_control_center.preview import ExecutionPreview, IntendedAction, preview_action
from local_ai_control_center.profiler import SystemProfile, profile_system
from local_ai_control_center.provider import (
    MockProvider,
    OllamaProvider,
    Provider,
    ProviderError,
)
from local_ai_control_center.run import new_run_id
from local_ai_control_center.skill import (
    CritiqueFileSkill,
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

DEFAULT_CONFIG_PATH = Path("config.yaml")

_SKILLS: dict[str, Skill] = {
    "summarize_file": SummarizeFileSkill(),
    "critique_file": CritiqueFileSkill(),
    "revise_file": ReviseFileSkill(),
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
    """Load configuration and build the workspace, or exit on failure."""
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
    preview = preview_action(plan.action, grant_for(resolved, config), config, workspace)
    if not _confirm(preview):
        console.print("[yellow]Declined.[/yellow] Nothing was run.")
        return

    generating = provider_choice is ProviderChoice.ollama
    try:
        if generating:
            with console.status("Contacting Ollama...") as status:
                status.update(
                    "Generating... (the first run loads the model into memory and may take longer)"
                )
                result = _do_run(resolved, tuple(requests), config, workspace, provider, audit)
        else:
            result = _do_run(resolved, tuple(requests), config, workspace, provider, audit)
    except (ProviderError, ReadError, PromptTooLargeError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    _report(result)
    _warn_about_the_answer(result, config)
    if config.context_tokens is None:
        _warn_no_context_ceiling()


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
    return OllamaProvider(config.model, config.context_tokens)


def _do_run(
    resolved: Skill,
    requests: tuple[str, ...],
    config: Config,
    workspace: Workspace,
    provider: Provider,
    audit: AuditLog,
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
        new_run_id(),
        lambda _preview: True,
        _approve,
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
    result = preview_action(plan.action, grant_for(resolved, config), config, workspace)
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

    _report_ingestion(result, target)


def _report_ingestion(result: RunResult, destination: Path) -> None:
    """Print the outcome of an ingestion run, naming the file it produced."""
    if result.outcome == "completed":
        console.print(Panel(f"Extracted text written to {destination}", title="Ingested"))
    elif result.outcome == "refused":
        _exit_refused()
    else:
        console.print("[yellow]Declined.[/yellow] Nothing was written.")


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


def main() -> None:
    """Entry point for the `lacc` console script."""
    app()
