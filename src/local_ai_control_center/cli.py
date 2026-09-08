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

from local_ai_control_center.audit import AuditLog
from local_ai_control_center.config import Config, load_config
from local_ai_control_center.converter import ConversionError, converter_for
from local_ai_control_center.cycle import ReadError, RunResult, run_conversion
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
    Skill,
    SummarizeFileSkill,
    grant_for,
    run_skill,
)
from local_ai_control_center.workspace import Workspace, workspace_from_config

DEFAULT_CONFIG_PATH = Path("config.yaml")

_SKILLS: dict[str, Skill] = {
    "summarize_file": SummarizeFileSkill(),
    "critique_file": CritiqueFileSkill(),
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


def _load(config_path: Path) -> tuple[Config, Workspace]:
    """Load configuration and build the workspace, or exit on failure."""
    try:
        config = load_config(config_path)
    except (OSError, ValueError) as error:
        console.print(f"[red]Could not load configuration:[/red] {error}")
        raise typer.Exit(code=1) from error
    workspace = workspace_from_config(config)
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
    request: Annotated[str, typer.Argument(help="The skill's input (e.g. a file path).")],
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

    plan = resolved.plan(request, config)
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
                result = _do_run(resolved, request, config, workspace, provider, audit)
        else:
            result = _do_run(resolved, request, config, workspace, provider, audit)
    except (ProviderError, ReadError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error

    _report(result)


def _build_provider(choice: ProviderChoice, config: Config) -> Provider:
    """Construct the chosen provider. Ollama needs a configured model; the mock does not."""
    if choice is ProviderChoice.mock:
        return MockProvider()
    return OllamaProvider(config.model)


def _do_run(
    resolved: Skill,
    request: str,
    config: Config,
    workspace: Workspace,
    provider: Provider,
    audit: AuditLog,
) -> RunResult:
    """Run the skill through the cycle with confirmation already handled."""
    return run_skill(
        resolved,
        request,
        grant_for(resolved, config),
        config,
        workspace,
        provider,
        audit,
        new_run_id(),
        lambda _preview: True,
    )


@app.command()
def preview(
    skill: Annotated[str, typer.Argument(help="Name of the skill to preview.")],
    request: Annotated[str, typer.Argument(help="The skill's input (e.g. a file path).")],
    config_path: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to the configuration file."),
    ] = DEFAULT_CONFIG_PATH,
) -> None:
    """Show what a skill would do, without asking, executing, or recording."""
    resolved = _resolve_skill(skill)
    config, workspace = _load(config_path)
    plan = resolved.plan(request, config)
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
        targets=(source, target),
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
def profile() -> None:
    """Detect and report what this machine offers, without changing anything."""
    result = profile_system()
    _show_profile(result)


def _show_profile(profile: SystemProfile) -> None:
    """Render a system profile with Rich."""
    if profile.engine_present:
        if profile.installed_models:
            lines = [
                f"- {model.name}  ({model.size_gb} GB, {model.quantization})"
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

    for note in profile.notes:
        console.print(f"[yellow]note:[/yellow] {note}")


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
