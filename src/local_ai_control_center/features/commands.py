"""What the commands are, read from the application that registers them (ADR-072).

**Derived, never listed.** A second copy of the command list would be a second writer of the
same thing, and this project already measured what that costs: two writers of the corpus
format drifted apart with the suite green and stripped the meaning from a real corpus
(ADR-065). The commands here come from the object the CLI actually builds, so a command that
is added appears and one that is renamed changes.

**And it does not import the CLI.** The application is passed in. This reads it by attribute,
which means a view is not importing another view, a slice keeps its rule of reaching only for
core and ports, and the whole thing is testable against a plain object that has the same
shape.
"""

from __future__ import annotations

import inspect
from typing import Any

from pydantic import BaseModel, ConfigDict


class Parameter(BaseModel):
    """One thing a command takes."""

    model_config = ConfigDict(frozen=True)

    name: str
    required: bool
    """True when it has no default, which is what makes it an argument rather than an option."""

    @property
    def shown(self) -> str:
        """How it is written on a command line."""
        return self.name if self.required else f"--{self.name.replace('_', '-')}"


class Command(BaseModel):
    """One command, as its own docstring describes it."""

    model_config = ConfigDict(frozen=True)

    name: str
    summary: str = ""
    """The first line of the docstring: what it does, in one sentence."""

    detail: str = ""
    """The rest, which in this project is usually why it behaves the way it does."""

    parameters: tuple[Parameter, ...] = ()

    @property
    def usage(self) -> str:
        """The line somebody would type."""
        return " ".join(["lacc", self.name, *(p.shown for p in self.parameters)])


_SKIP = {"config_path"}
"""Taken by nearly every command and never the point of any of them."""


def _described(documentation: str | None) -> tuple[str, str]:
    """Split a docstring into its opening sentence and the rest, both tidied."""
    if not documentation:
        return "", ""
    cleaned = inspect.cleandoc(documentation)
    parts = cleaned.split("\n\n", 1)
    summary = " ".join(parts[0].split())
    rest = parts[1].strip() if len(parts) > 1 else ""
    return summary, rest


def _parameters_of(function: Any) -> tuple[Parameter, ...]:
    """What a command takes, from its signature rather than from its decorators.

    A required parameter is one with no default. That is what Typer uses to tell an argument
    from an option too, so the two agree without this knowing anything about Typer.
    """
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return ()
    return tuple(
        Parameter(name=name, required=parameter.default is inspect.Parameter.empty)
        for name, parameter in signature.parameters.items()
        if name not in _SKIP
    )


def commands_of(application: Any) -> tuple[Command, ...]:
    """Every command the application registers, in alphabetical order.

    Reads `registered_commands` by attribute. An object that does not have it yields
    nothing, which is what should happen rather than an exception in a window.
    """
    registered = getattr(application, "registered_commands", None)
    if not isinstance(registered, list):
        return ()
    found: list[Command] = []
    for entry in registered:
        function = getattr(entry, "callback", None)
        if function is None:
            continue
        # Typer names a command after its function when nothing else is given, with
        # underscores becoming hyphens. Matching that exactly is what keeps this honest -
        # including for a name that would come out oddly, because the point is to say what
        # the CLI answers to rather than what it ought to.
        name = getattr(entry, "name", None) or function.__name__.replace("_", "-")
        summary, detail = _described(function.__doc__)
        found.append(
            Command(
                name=name,
                summary=summary,
                detail=detail,
                parameters=_parameters_of(function),
            )
        )
    return tuple(sorted(found, key=lambda command: command.name))
