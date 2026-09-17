"""Skills written down in a file, and the parts a file may not decide (ADR-048)."""

from __future__ import annotations

from pathlib import Path

import pytest

from local_ai_control_center.core.config import Config
from local_ai_control_center.core.declared import (
    DeclarationError,
    DeclaredField,
    DeclaredSkill,
    FileSkill,
    load_declared_skills,
    prompt_for,
)
from local_ai_control_center.core.fence import CONTENT_PLACEHOLDER
from local_ai_control_center.core.grounding import check_answer

NL = chr(10)


def _declared(**overrides: object) -> DeclaredSkill:
    base: dict[str, object] = {
        "name": "assumptions",
        "summary": "List what a paper takes for granted",
        "instructions": "Find the assumptions it never defends.",
        "fields": [
            DeclaredField(name="assumption", describe="what it takes for granted"),
            DeclaredField(name="evidence", describe="the exact words", quotation=True),
            DeclaredField(name="page", describe="the page", required=False),
        ],
    }
    base.update(overrides)
    return DeclaredSkill.model_validate(base)


def test_the_structure_is_built_by_lacc_from_the_declared_fields() -> None:
    """The measured half. Structure is obeyed; an author is not handed that part."""
    built = prompt_for(_declared(), Config(workspace_root=Path(".")))
    assert "ASSUMPTION: what it takes for granted" in built
    assert "EVIDENCE: the exact words" in built
    assert "PAGE: the page   (optional)" in built
    assert "One block per entry" in built


def test_the_instruction_is_restated_after_the_document() -> None:
    """Not a style choice: stating the format before a long document lost two claims in
    three, and moving it after tripled them (ADR-037)."""
    built = prompt_for(_declared(), Config(workspace_root=Path(".")))
    assert built.index(CONTENT_PLACEHOLDER) < built.index("Use this format")


def test_a_quotation_field_asks_for_the_documents_own_words() -> None:
    built = prompt_for(_declared(), Config(workspace_root=Path(".")))
    assert "The EVIDENCE must be the document's own words" in built
    assert "it will be checked against the document" in built


def test_a_skill_with_no_quotation_field_is_not_checked() -> None:
    plain = _declared(fields=[DeclaredField(name="note", describe="a note")])
    assert not plain.verifies
    assert plain.quoted_field == ""
    built = prompt_for(plain, Config(workspace_root=Path(".")))
    assert "checked against the document" not in built


def test_the_declared_field_is_what_gets_checked(tmp_path: Path) -> None:
    """The load-bearing one: a declaration chooses the label, never the checking."""
    source = f"<!-- page 1 -->{NL}{NL}The model assumes the cohort is representative."
    answer = (
        f"ASSUMPTION: representativeness{NL}"
        f"EVIDENCE: The model assumes the cohort is representative.{NL}"
        f"PAGE: 1{NL}{NL}"
        f"ASSUMPTION: something invented{NL}"
        f"EVIDENCE: A sentence that is nowhere in the paper.{NL}"
        f"PAGE: 2"
    )
    plan = FileSkill(_declared()).plan(("p.md",), Config(workspace_root=tmp_path))
    checked = check_answer(answer, source, plan.fields, plan.quote_field)

    assert [c.found for c in checked] == [True, False]
    assert checked[0].claim.claim == "representativeness"
    assert checked[0].found_on_page == 1


def test_a_declaration_cannot_ask_for_more_than_reading() -> None:
    """A file that could widen its own permissions would make the system advisory."""
    assert FileSkill(_declared()).required == frozenset({"read_files"})
    assert FileSkill(_declared(reads_files=False)).required == frozenset()


def test_two_fields_cannot_both_be_the_quotation() -> None:
    with pytest.raises(ValueError, match="Only one field"):
        _declared(
            fields=[
                DeclaredField(name="one", quotation=True),
                DeclaredField(name="two", quotation=True),
            ]
        )


def test_two_fields_cannot_share_a_name() -> None:
    with pytest.raises(ValueError, match="share a name"):
        _declared(fields=[DeclaredField(name="same"), DeclaredField(name="same")])


@pytest.mark.parametrize("bad", ["", "   ", "has spaces", "punctuation!", "a" * 41])
def test_an_unusable_skill_name_is_refused(bad: str) -> None:
    with pytest.raises(ValueError):
        _declared(name=bad)


def test_a_skill_must_ask_for_something() -> None:
    with pytest.raises(ValueError):
        _declared(fields=[])


def _write(folder: Path, name: str, body: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(body, encoding="utf-8")


def test_declarations_load_from_beside_the_configuration(tmp_path: Path) -> None:
    config = tmp_path / "lacc.yaml"
    config.write_text("workspace_root: .", encoding="utf-8")
    _write(
        tmp_path / "skills",
        "one.yaml",
        f"name: mine{NL}summary: s{NL}instructions: i{NL}fields:{NL}  - name: note{NL}",
    )
    loaded = load_declared_skills(config)
    assert [skill.name for skill in loaded] == ["mine"]


def test_no_skills_folder_is_not_an_error(tmp_path: Path) -> None:
    """A project with no declared skills is the ordinary case, not a broken one."""
    config = tmp_path / "lacc.yaml"
    config.write_text("workspace_root: .", encoding="utf-8")
    assert load_declared_skills(config) == ()


def test_an_unreadable_declaration_is_an_error_rather_than_a_skip(tmp_path: Path) -> None:
    """A skill that silently did not load is one somebody runs and gets the wrong answer."""
    config = tmp_path / "lacc.yaml"
    config.write_text("workspace_root: .", encoding="utf-8")
    _write(tmp_path / "skills", "broken.yaml", "name: [this is not a name]")
    with pytest.raises(DeclarationError, match="broken.yaml"):
        load_declared_skills(config)


def test_two_declarations_sharing_a_name_are_refused(tmp_path: Path) -> None:
    config = tmp_path / "lacc.yaml"
    config.write_text("workspace_root: .", encoding="utf-8")
    body = f"name: same{NL}summary: s{NL}instructions: i{NL}fields:{NL}  - name: note{NL}"
    _write(tmp_path / "skills", "a.yaml", body)
    _write(tmp_path / "skills", "b.yaml", body)
    with pytest.raises(DeclarationError, match="share a name"):
        load_declared_skills(config)
