"""What each skill actually asks the model, before anything is asked (ADR-074).

The single most useful thing this project can show about itself. Every measured finding here
is about the difference between what somebody meant to ask and what was sent: an instruction
not to guess that produced twelve invented journal names, a schema that delivered the shape
and lost the answer, a declared skill whose prompt never carried the question at all - which
was invisible for as long as nobody looked at the prompt.

**A plan is pure and has always been pure**, which is why this costs nothing. `Skill.plan`
produces the template with no effects, the cycle fills it later, and reading one runs no
model and reaches no engine (ADR-014).

The skills are passed in rather than gathered here: assembling them reads files and reports
failures, which is the caller's job.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from local_ai_control_center.core.config import Config
from local_ai_control_center.core.fence import CONTENT_PLACEHOLDER
from local_ai_control_center.core.skill import Skill

WHERE_THE_DOCUMENT_GOES = "\n────────  your document is inserted here  ────────\n"
"""What the hole in a template is shown as.

The placeholder is a marker nobody would recognise, and leaving it raw would make the one
important thing about a prompt - that the document arrives *inside* it, surrounded by
instructions - the least visible thing on the page (ADR-038).
"""

EXAMPLE_DOCUMENT = "your-document.md"
"""Stood in for the real filename, so a template can be read before choosing a file."""


class Prompt(BaseModel):
    """One skill's request, as it would be sent."""

    model_config = ConfigDict(frozen=True)

    skill: str
    summary: str = ""
    """The skill's own first line, which says what it is for."""

    template: str = ""
    """The prompt with the document's place marked, or the reason it could not be planned."""

    planned: bool = True
    needs: tuple[str, ...] = ()
    """The capabilities the skill declares, which is what a preview would ask you to allow."""

    checks_quotes: bool = False
    fields: tuple[str, ...] = ()
    """The labels the answer is asked to carry, in order (ADR-048)."""

    temperature: float | None = None

    @property
    def words(self) -> int:
        """How long the instruction is, before any document is added to it."""
        return len(self.template.split())


def _first_line(documentation: str | None) -> str:
    """A skill's opening sentence, or nothing."""
    if not documentation:
        return ""
    for line in documentation.strip().splitlines():
        if line.strip():
            return " ".join(line.split())
    return ""


def readable(template: str) -> str:
    """The template with the document's place shown rather than marked."""
    return template.replace(CONTENT_PLACEHOLDER, WHERE_THE_DOCUMENT_GOES)


def prompts_of(
    skills: Mapping[str, Skill], config: Config, example: str = EXAMPLE_DOCUMENT
) -> tuple[Prompt, ...]:
    """Every skill's prompt, planned against one example document.

    A skill whose plan cannot be made carries the reason instead of a template. That is a
    thing worth seeing: a skill that cannot be planned is a skill that will fail when it is
    run, and this is the cheaper place to find out.
    """
    found: list[Prompt] = []
    for name, skill in sorted(skills.items()):
        summary = _first_line(type(skill).__doc__)
        needs = tuple(sorted(skill.required))
        try:
            plan = skill.plan((example,), config)
        except Exception as error:  # noqa: BLE001 - a skill may refuse for any reason
            found.append(
                Prompt(
                    skill=name,
                    summary=summary,
                    template=f"This skill could not be planned: {error}",
                    planned=False,
                    needs=needs,
                )
            )
            continue
        found.append(
            Prompt(
                skill=name,
                summary=summary,
                template=readable(plan.prompt_template),
                needs=needs,
                checks_quotes=plan.verify_quotes,
                fields=plan.fields,
                temperature=getattr(plan, "temperature", None),
            )
        )
    return tuple(found)
