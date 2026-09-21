"""Reading the commands off the application that registers them (ADR-072)."""

from __future__ import annotations

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


def test_a_required_parameter_is_an_argument_and_the_rest_are_options() -> None:
    command = commands_of(_App(_Entry(example)))[0]
    assert command.parameters == (
        Parameter(name="source", required=True),
        Parameter(name="into", required=False),
    )
    assert command.usage == "lacc example source --into"


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
