"""Reading the commands off the application that registers them (ADR-072)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any

import typer
import typer.main

from local_ai_control_center.features.commands import Command, Parameter, commands_of


class _Entry:
    """What a Typer application holds for one command, as far as this reads it."""

    def __init__(self, callback: object, name: str | None = None) -> None:
        self.callback = callback
        self.name = name


class _App:
    def __init__(self, *entries: _Entry) -> None:
        self.registered_commands = list(entries)


def example(source: str, into: str = "out.md") -> None:
    """Do the thing in one line.

    And then the reason it behaves the way it does, which in this project is
    usually the longer half.
    """


def test_a_command_is_named_the_way_typer_names_it() -> None:
    """Underscores become hyphens, which is what the CLI actually answers to."""

    def engine_test() -> None:
        """Check the engine."""

    assert commands_of(_App(_Entry(engine_test)))[0].name == "engine-test"


def test_an_explicit_name_wins() -> None:
    def whatever() -> None:
        """Something."""

    assert commands_of(_App(_Entry(whatever, name="given")))[0].name == "given"


def test_the_first_sentence_and_the_rest_are_kept_apart() -> None:
    command = commands_of(_App(_Entry(example)))[0]
    assert command.summary == "Do the thing in one line."
    assert command.detail.startswith("And then the reason")


def test_without_a_declaration_typer_s_own_rule_decides() -> None:
    """No default makes an argument and a default makes an option - Typer's rule, and this one."""
    command = commands_of(_App(_Entry(example)))[0]
    assert command.parameters == (
        Parameter(name="source", required=True),
        Parameter(name="into", required=False, flag="--into"),
    )
    assert command.usage == "lacc example <source>"


def review(
    draft: Annotated[Path, typer.Argument(help="Yours.")],
    against: Annotated[Path, typer.Option("--against", help="Theirs.")],
    into: Annotated[Path | None, typer.Option("--into", help="Where.")] = None,
    cited: Annotated[bool, typer.Option("--cited", help="Also these.")] = False,
) -> None:
    """Read a draft against a corpus."""


def test_a_required_option_keeps_its_flag_and_shows_what_it_takes() -> None:
    """Found using the window: `lacc review draft against --into` was copied and did not run.

    Being required does not make a thing an argument. `--against` is required and an option,
    and the line printed it as a bare word, with no mark anywhere of what to fill in.
    """
    command = commands_of(_App(_Entry(review)))[0]
    assert command.usage == "lacc review <draft> --against <against>"
    optional = [p.shown for p in command.parameters if not p.required]
    assert optional == ["--into <into>", "--cited"]


def test_every_line_the_window_offers_to_copy_parses_once_filled_in() -> None:
    """The copy button's promise, held against the CLI's own parser.

    Each usage line has its placeholders filled and is handed to the parser of the command it
    names - which parses and converts and runs nothing, so a command that opens a window is as
    safe to check as one that reads a file. The line printed before this record fails here:
    `Option '--into' requires an argument`.
    """
    from local_ai_control_center.cli import app

    parsers = typer.main.get_command(app)
    for command in commands_of(app):
        # A group's command is two words, `engine test`, and its parser is inside the group's.
        names = command.name.split()
        parser: Any = parsers
        for name in names:
            parser = parser.commands[name]
        words = command.usage.split()[1 + len(names) :]
        filled = [re.sub(r"<[^>]+>", "x", word) for word in words]
        parser.make_context(command.name, filled)


def test_the_commands_of_a_group_are_listed_by_their_whole_name() -> None:
    """Commands said 21 where `lacc --help` lists 23: `engine` and `notify` were left out."""
    from local_ai_control_center.cli import app

    names = [command.name for command in commands_of(app)]
    assert "engine test" in names and "notify test" in names
    groups = sum(len(group.typer_instance.registered_commands) for group in app.registered_groups)
    assert len(names) == len(app.registered_commands) + groups


def test_the_configuration_option_is_left_out() -> None:
    """Nearly every command takes it and it is the point of none of them."""

    def something(source: str, config_path: str = "c.yaml") -> None:
        """Does something."""

    assert [p.name for p in commands_of(_App(_Entry(something)))[0].parameters] == ["source"]


def test_an_object_of_the_wrong_shape_yields_nothing_rather_than_raising() -> None:
    """This runs inside a window, where an exception is a blank panel."""
    assert commands_of(object()) == ()
    assert commands_of(_App()) == ()


def test_the_real_application_describes_every_command_it_registers() -> None:
    """The point of deriving rather than listing: this cannot go stale.

    Run against the CLI itself. A command added without a docstring fails here, which is the
    same rule the rest of this codebase is held to.
    """
    from local_ai_control_center.cli import app

    commands = commands_of(app)
    assert len(commands) > 10
    names = {command.name for command in commands}
    assert {"ask", "collect", "corpus", "review", "resolve", "window"} <= names
    for command in commands:
        assert command.summary, f"{command.name} has no first line"
        assert isinstance(command, Command)
