"""Command-line interface: the `lacc` command.

The first human interface to the system (ADR-010). Built with Typer and rendered
with Rich, both confined here so the core stays free of interface code. `run` plans
a skill, previews it, asks for confirmation (defaulting to no), and executes;
`preview` shows what would happen without doing it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from local_ai_control_center.audit import AuditLog
from local_ai_control_center.config import Config, load_config
from local_ai_control_center.cycle import RunResult
from local_ai_control_center.permissions import Permissions
from local_ai_control_center.preview import ExecutionPreview, preview_action
from local_ai_control_center.provider import MockProvider
from local_ai_control_center.run import new_run_id
from local_ai_control_center.skill import Skill, SummarizeFileSkill, run_skill
from local_ai_control_center.workspace import Workspace, workspace_from_config

DEFAULT_CONFIG_PATH = Path("config.yaml")

_SKILLS: dict[str, Skill] = {
    "summarize_file": SummarizeFileSkill(),
}

app = typer.Typer(
    help="Local AI Control Center - run AI-assisted skills with control and audit.",
    no_args_is_help=True,
)
console = Console()


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
) -> None:
    """Plan a skill, preview it, confirm, then execute and record it."""
    resolved = _resolve_skill(skill)
    config, workspace = _load(config_path)
    audit = AuditLog(workspace, config)
    result = run_skill(
        resolved,
        request,
        Permissions(read_files=True),
        config,
        workspace,
        MockProvider(),
        audit,
        new_run_id(),
        _confirm,
    )
    _report(result)


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
    plan = resolved.plan(request)
    result = preview_action(plan.action, Permissions(read_files=True), config, workspace)
    _show_preview(result)


def _report(result: RunResult) -> None:
    """Print the outcome of a run."""
    if result.outcome == "completed" and result.completion is not None:
        console.print(Panel(result.completion.text, title="Result", expand=False))
    elif result.outcome == "refused":
        console.print("[red]Refused:[/red] the action would not be allowed.")
    elif result.outcome == "declined":
        console.print("[yellow]Declined.[/yellow] Nothing was run.")


def main() -> None:
    """Entry point for the `lacc` console script."""
    app()
