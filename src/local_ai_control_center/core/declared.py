"""Skills written down in a file rather than in code (ADR-048).

What is declarable is deliberately narrow. An author says what to ask for and what shape the
answer takes; LACC builds the structure, keeps the permission ceiling, and does the checking.

The division is not fussiness, it is the measurement. Asked to cover twenty-four documents a
model covered ten; given the same request as a skeleton with twenty-four slots it returned
twenty-three; told explicitly in the same prompt not to invent a field it invented twelve.
**Structure is obeyed and instruction is negotiated**, so the structure is the part LACC must
not hand over.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import Config
from .fence import CONTENT_PLACEHOLDER
from .permissions import Capability
from .preview import IntendedAction
from .skill import Skill, SkillPlan

_DECLARABLE: frozenset[Capability] = frozenset({"read_files"})
"""What a declared skill may ask for.

Reading, and nothing else. Writing files, reaching the network and running commands are
effects whose blast radius is not obvious from a prompt, and a file that could request them
would make the permission system a suggestion. A built-in skill argues for more in an ADR;
a declaration cannot argue.
"""

_LONGEST_NAME = 40
_MOST_FIELDS = 12


class DeclaredField(BaseModel):
    """One thing a declared skill asks the model to return."""

    model_config = ConfigDict(frozen=True)

    name: str
    describe: str = ""
    """What the field means, shown to the model beside its label."""

    required: bool = True
    """Whether a block missing this field is dropped rather than kept."""

    quotation: bool = False
    """Whether this field carries words copied from the document.

    At most one field may say so, and saying so is what opts into the existing check - the
    same one `extract_claims` uses. A declaration cannot define a new kind of checking,
    because a check nobody reviewed reports confidence it has not earned (ADR-048).
    """

    @field_validator("name")
    @classmethod
    def _usable_as_a_label(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned or not cleaned.replace("_", "").isalnum():
            raise ValueError(f"'{value}' is not a usable field name: letters, digits and _.")
        return cleaned


class DeclaredSkill(BaseModel):
    """A skill an author wrote down, with the parts LACC keeps left out.

    Frozen, and validated on the way in rather than trusted: a file is not a review.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    summary: str
    instructions: str
    fields: tuple[DeclaredField, ...] = Field(min_length=1, max_length=_MOST_FIELDS)
    reads_files: bool = True
    """Whether the skill is given documents. The only capability a declaration may ask for."""

    over: Literal["document", "corpus"] = "document"
    """What the skill works on: a document you name, or passages retrieved from a corpus.

    A corpus skill is how drafting and organising become possible without new code. Its
    material is quotations already checked against the documents they came from, so prose
    built on them has claims that are traceable even though the prose itself is not - which
    is the most this project can offer for writing, and worth being plain about.

    A corpus skill declares no targets: the passages are chosen for it, so it needs no
    capability at all and `reads_files` does not apply.
    """

    @property
    def over_a_corpus(self) -> bool:
        """Whether its material is retrieved rather than named."""
        return self.over == "corpus"

    @field_validator("name")
    @classmethod
    def _usable_as_a_command(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned or len(cleaned) > _LONGEST_NAME:
            raise ValueError("A skill name must be one to forty characters.")
        if not cleaned.replace("_", "").replace("-", "").isalnum():
            raise ValueError(f"'{value}' is not a usable skill name: letters, digits, - and _.")
        return cleaned

    @field_validator("fields")
    @classmethod
    def _at_most_one_quotation(cls, value: tuple[DeclaredField, ...]) -> tuple[DeclaredField, ...]:
        quoting = [field.name for field in value if field.quotation]
        if len(quoting) > 1:
            raise ValueError(
                f"Only one field can carry the quotation; this names {len(quoting)}: "
                + ", ".join(quoting)
            )
        names = [field.name for field in value]
        if len(set(names)) != len(names):
            raise ValueError("Two fields share a name, and the answer could not be read back.")
        return value

    @property
    def quoted_field(self) -> str:
        """The field whose words are checked against the document, or empty."""
        return next((field.name for field in self.fields if field.quotation), "")

    @property
    def verifies(self) -> bool:
        """Whether this skill's answers can be checked rather than trusted."""
        return bool(self.quoted_field)


class FileSkill(Skill):
    """A declared skill, presented to the cycle exactly as a built-in one is.

    The cycle cannot tell the difference and must not: a declared skill goes through the same
    preview, the same confirmation and the same permission ceiling. What differs is that
    nobody reviewed its wording, which the CLI says out loud rather than leaving to be
    noticed (ADR-048).
    """

    def __init__(self, declared: DeclaredSkill) -> None:
        """Wrap a validated declaration."""
        self._declared = declared

    @property
    def declared(self) -> DeclaredSkill:
        """The declaration this was built from."""
        return self._declared

    @property
    def name(self) -> str:
        """Identify this skill by the name its file gave it."""
        return self._declared.name

    @property
    def required(self) -> frozenset[Capability]:
        """What it needs, intersected with what a declaration is allowed to ask for."""
        if self._declared.over_a_corpus:
            return frozenset()  # The passages are handed to it; it opens nothing.
        asked: frozenset[Capability] = (
            frozenset({"read_files"}) if self._declared.reads_files else frozenset()
        )
        return asked & _DECLARABLE

    def plan(self, requests: tuple[str, ...], config: Config) -> SkillPlan:
        """Turn the declaration into a plan. Pure, like every other skill's."""
        action = IntendedAction(
            name=self.name,
            summary=f"{self._declared.summary} ({chr(44).join(requests)})"
            if requests
            else self._declared.summary,
            required=self.required,
            targets=(
                tuple(Path(item) for item in requests)
                if self._declared.reads_files and not self._declared.over_a_corpus
                else ()
            ),
        )
        return SkillPlan(
            action=action,
            prompt_template=prompt_for(self._declared, config),
            verify_quotes=self._declared.verifies,
            fields=tuple(field.name for field in self._declared.fields),
            quote_field=self._declared.quoted_field,
        )


def prompt_for(declared: DeclaredSkill, config: Config) -> str:
    """Build the prompt from a declaration: the author's words, LACC's shape.

    The instructions are restated **after** the document rather than before it, which is not
    a style choice - stating the format thousands of tokens from the point of generation
    tripled the claims a model returned when it was fixed (ADR-037). An author writing their
    own prompt would not know to do that, which is why they do not write this part.
    """
    break_ = chr(10)
    labels = break_.join(
        f"{field.name.upper()}: {field.describe or field.name}"
        + ("" if field.required else "   (optional)")
        for field in declared.fields
    )
    quoting = declared.quoted_field
    fidelity = (
        break_ + f"The {quoting.upper()} must be the document's own words, copied character for "
        "character. A quotation you adjust, tidy or translate is no longer a quotation, and "
        "it will be checked against the document."
        if quoting
        else ""
    )
    if declared.over_a_corpus:
        document = (
            break_
            * 2
            + "Below are passages taken from a set of documents. Every one has been checked: "
            "the words are really in the document named beside it. Use only these, and quote "
            "nothing you do not see here." + break_ * 2 + CONTENT_PLACEHOLDER + break_ * 2
        )
    elif declared.reads_files:
        document = break_ * 2 + CONTENT_PLACEHOLDER + break_ * 2
    else:
        document = break_ * 2
    return (
        declared.instructions.strip()
        + break_ * 2
        + f"Answer in {config.output_language}."
        + fidelity
        + document
        + "Use this format, and nothing else:"
        + break_ * 2
        + labels
        + break_ * 2
        + "One block per entry, separated by a blank line. No preamble, no numbering, no "
        + "commentary."
    )


SKILLS_DIRECTORY = "skills"
"""Where declarations live: a folder beside the configuration file.

Beside the configuration and **never inside the workspace**. The workspace holds documents,
some of them downloaded, and `write_files` can put things there. A prompt is an instruction
to a model, and instructions must not live where the material lives (ADR-048).
"""


class DeclarationError(Exception):
    """Raised when a skill file cannot be read, or says something it may not say."""


def load_declared_skills(beside: Path) -> tuple[FileSkill, ...]:
    """Load every declaration from the `skills/` folder beside ``beside``.

    Returns nothing when the folder is absent, which is the ordinary case: a project with no
    declared skills is not a broken one. A single unreadable file is an error rather than a
    skip, because a skill that silently did not load is a skill somebody will run and get the
    wrong one.
    """
    folder = beside.parent / SKILLS_DIRECTORY
    if not folder.is_dir():
        return ()
    found: list[FileSkill] = []
    for path in sorted(folder.glob("*.yaml")) + sorted(folder.glob("*.yml")):
        found.append(FileSkill(declaration_in(path)))
    names = [skill.name for skill in found]
    if len(set(names)) != len(names):
        raise DeclarationError(
            f"Two declarations in {folder} share a name, and running one would be a coin toss."
        )
    return tuple(found)


def declaration_in(path: Path) -> DeclaredSkill:
    """Read and validate one declaration, naming the file in anything that goes wrong."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise DeclarationError(f"Cannot read {path.name}: {error}") from error
    if not isinstance(raw, dict):
        raise DeclarationError(f"{path.name} is not a skill declaration: it holds no fields.")
    try:
        return DeclaredSkill.model_validate(raw)
    except ValueError as error:
        raise DeclarationError(f"{path.name}: {error}") from error
