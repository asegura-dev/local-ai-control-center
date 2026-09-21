"""Reading what a skill would ask, before it asks it (ADR-074)."""

from __future__ import annotations

from pathlib import Path

from local_ai_control_center.core.config import Config
from local_ai_control_center.core.fence import CONTENT_PLACEHOLDER
from local_ai_control_center.core.permissions import Capability
from local_ai_control_center.core.preview import IntendedAction
from local_ai_control_center.core.skill import Skill, SkillPlan
from local_ai_control_center.features.prompts import (
    WHERE_THE_DOCUMENT_GOES,
    prompts_of,
    readable,
)


def _config(tmp_path: Path) -> Config:
    return Config(workspace_root=tmp_path)


class _Simple(Skill):
    """Does a simple thing to a document."""

    @property
    def name(self) -> str:
        return "simple"

    @property
    def required(self) -> frozenset[Capability]:
        return frozenset({"read_files"})

    def plan(self, requests: tuple[str, ...], config: Config) -> SkillPlan:
        return SkillPlan(
            action=IntendedAction(
                name="simple",
                summary=f"read {requests[0]}",
                required=frozenset({"read_files"}),
                targets=(Path(requests[0]),),
            ),
            prompt_template=f"Read this.{CONTENT_PLACEHOLDER}Answer briefly.",
            verify_quotes=True,
        )


class _Refuses(Skill):
    """Cannot be planned at all."""

    @property
    def name(self) -> str:
        return "refuses"

    @property
    def required(self) -> frozenset[Capability]:
        return frozenset()

    def plan(self, requests: tuple[str, ...], config: Config) -> SkillPlan:
        raise ValueError("this skill needs two documents")


def test_the_document_hole_is_shown_rather_than_left_as_a_marker() -> None:
    """The one important thing about a prompt is that the document arrives inside it."""
    assert readable(f"before{CONTENT_PLACEHOLDER}after") == (
        f"before{WHERE_THE_DOCUMENT_GOES}after"
    )


def test_a_prompt_carries_what_a_preview_would_ask_you_to_allow(tmp_path: Path) -> None:
    prompt = prompts_of({"simple": _Simple()}, _config(tmp_path))[0]
    assert prompt.skill == "simple"
    assert prompt.summary == "Does a simple thing to a document."
    assert prompt.needs == ("read_files",)
    assert prompt.checks_quotes
    assert WHERE_THE_DOCUMENT_GOES in prompt.template
    assert prompt.planned


def test_a_skill_that_cannot_be_planned_says_so_instead_of_vanishing(tmp_path: Path) -> None:
    """A skill that cannot be planned will fail when run. This is the cheaper place."""
    prompt = prompts_of({"refuses": _Refuses()}, _config(tmp_path))[0]
    assert not prompt.planned
    assert "two documents" in prompt.template


def test_the_length_is_the_instruction_alone(tmp_path: Path) -> None:
    """How long the asking is, before any document is added to it."""
    prompt = prompts_of({"simple": _Simple()}, _config(tmp_path))[0]
    assert 0 < prompt.words < 30


def test_every_real_skill_can_be_read_this_way(tmp_path: Path) -> None:
    """Run against the skills the CLI actually offers, not against fixtures.

    A skill that cannot be planned against one ordinary document is reported rather than
    hidden, and this is where that shows up.
    """
    from local_ai_control_center.cli import _SKILLS

    prompts = prompts_of(_SKILLS, _config(tmp_path))
    assert len(prompts) >= 4
    for prompt in prompts:
        assert prompt.skill
        assert prompt.template, f"{prompt.skill} produced no template at all"
