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
import typing
from typing import Any

from pydantic import BaseModel, ConfigDict


class Parameter(BaseModel):
    """One thing a command takes."""

    model_config = ConfigDict(frozen=True)

    name: str
    required: bool
    """True when it has no default: the command does not run without it."""

    flag: str = ""
    """How an option is named on a command line, `--into`; empty for an argument.

    Read from the declaration, because being required does not make a thing an argument.
    `review` requires `--against`, and a usage line that printed it as `against` could be
    copied and could not be run (ADR-103).
    """

    switch: bool = False
    """An option that takes no value, like `--cited`."""

    @property
    def shown(self) -> str:
        """How it is written on a command line, with the value it takes as a placeholder."""
        value = f"<{self.name.replace('_', '-')}>"
        if not self.flag:
            return value
        return self.flag if self.switch else f"{self.flag} {value}"


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
        """The line somebody would type: what the command cannot run without.

        What is optional is listed beside it rather than in it, so that a line copied from here
        and filled in is a line that runs.
        """
        needed = (p.shown for p in self.parameters if p.required)
        return " ".join(["lacc", self.name, *needed])


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


def _declared(hint: Any) -> tuple[str, str, bool]:
    """What an annotation declares - `argument`, `option` or nothing - its flag, and whether
    it is a switch.

    Read by the names of the objects Typer leaves in the annotation, so this knows the shape
    of a declaration without importing the library that makes it: presentation stays in the
    CLI. Declared with `Annotated`, the first name sits in `default` and the rest in
    `param_decls` - seen on the real application, not assumed.
    """
    if typing.get_origin(hint) is not typing.Annotated:
        return "", "", False
    base, *metadata = typing.get_args(hint)
    for declaration in metadata:
        kind = type(declaration).__name__
        if kind == "ArgumentInfo":
            return "argument", "", False
        if kind == "OptionInfo":
            first = getattr(declaration, "default", None)
            rest = getattr(declaration, "param_decls", None) or ()
            names = [n.split("/")[0] for n in (first, *rest) if isinstance(n, str)]
            return "option", next((n for n in names if n.startswith("--")), ""), base is bool
    return "", "", False


def _parameters_of(function: Any) -> tuple[Parameter, ...]:
    """What a command takes, from its signature and what its annotations declare.

    An annotation that declares an option or an argument says which it is. Without one, a
    parameter with no default is an argument and the rest are options, which is the rule
    Typer applies itself.
    """
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return ()
    try:
        hints = typing.get_type_hints(function, include_extras=True)
    except (NameError, TypeError, AttributeError):
        hints = {}
    found = []
    for name, parameter in signature.parameters.items():
        if name in _SKIP:
            continue
        required = parameter.default is inspect.Parameter.empty
        kind, flag, switch = _declared(hints.get(name))
        if not kind:
            kind = "argument" if required else "option"
            switch = isinstance(parameter.default, bool)
        if kind == "argument":
            found.append(Parameter(name=name, required=required))
            continue
        flag = flag or f"--{name.replace('_', '-')}"
        found.append(Parameter(name=name, required=required, flag=flag, switch=switch))
    return tuple(found)


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
