"""A shape the engine enforces, and the path that still works when it cannot (ADR-052)."""

from __future__ import annotations

import json
from pathlib import Path

from local_ai_control_center.core.config import Config
from local_ai_control_center.core.grounding import parse_claims
from local_ai_control_center.core.preview import ExecutionPreview, IntendedAction
from local_ai_control_center.core.skill import (
    AssessSourceSkill,
    ExtractClaimsSkill,
    SkillPlan,
    SummarizeFileSkill,
)

NL = chr(10)
Q = chr(34)


def _plan(**overrides: object) -> SkillPlan:
    base: dict[str, object] = {
        "action": IntendedAction(name="x", summary="s", required=frozenset()),
        "prompt_template": "t",
        "verify_quotes": True,
        "answer_is_entries_only": True,
    }
    base.update(overrides)
    return SkillPlan.model_validate(base)


def test_a_skill_that_does_not_enforce_a_shape_sends_none() -> None:
    """Off by default, and turned on per skill after measuring it."""
    assert _plan().output_schema is None


def test_the_schema_comes_from_the_fields_already_declared() -> None:
    """Nothing is authored twice: the skill already says what it asks for."""
    built = _plan(enforce_shape=True, fields=("point", "quote", "source")).output_schema
    assert built is not None
    entry = built["properties"]["entries"]["items"]
    assert set(entry["properties"]) == {"point", "quote", "source"}
    assert entry["required"] == ["point", "quote"], "the first field and the quotation"


def test_a_skill_with_no_quotation_field_requires_only_its_first() -> None:
    built = _plan(enforce_shape=True, fields=("note",), quote_field="").output_schema
    assert built is not None
    assert built["properties"]["entries"]["items"]["required"] == ["note"]


def test_an_answer_the_engine_shaped_is_read_back() -> None:
    answer = json.dumps(
        {
            "entries": [
                {"claim": "it was placed", "quote": "the exact words", "page": "7"},
                {"claim": "another", "quote": "more exact words"},
            ]
        }
    )
    claims = parse_claims(answer)
    assert [c.claim for c in claims] == ["it was placed", "another"]
    assert [c.page for c in claims] == [7, None]


def test_an_entry_missing_its_quotation_is_dropped_as_it_always_was() -> None:
    answer = json.dumps({"entries": [{"claim": "no words to check"}]})
    assert parse_claims(answer) == ()


def test_the_line_oriented_path_still_works() -> None:
    """Enforcement improves a path that works; it does not replace it. A provider that
    cannot constrain, or a model that ignores the schema, must still be parsed."""
    answer = f"CLAIM: from lines{NL}QUOTE: the exact words{NL}PAGE: 3"
    claims = parse_claims(answer)
    assert len(claims) == 1
    assert claims[0].claim == "from lines"
    assert claims[0].page == 3


def test_something_that_looks_like_json_and_is_not_falls_back_to_lines() -> None:
    """Returning None rather than an empty tuple is what makes the fallback possible."""
    answer = "{ this is not json at all" + NL + "CLAIM: a" + NL + "QUOTE: b"
    assert [c.claim for c in parse_claims(answer)] == ["a"]


def test_json_that_is_not_the_expected_shape_falls_back_too() -> None:
    answer = json.dumps({"something_else": [1, 2, 3]})
    assert parse_claims(answer) == ()


def test_declared_field_names_work_under_a_schema() -> None:
    answer = json.dumps(
        {"entries": [{"assumption": "taken for granted", "evidence": "the exact words"}]}
    )
    claims = parse_claims(answer, ("assumption", "evidence"), "evidence")
    assert len(claims) == 1
    assert claims[0].claim == "taken for granted"
    assert claims[0].quote == "the exact words"


def _preview() -> ExecutionPreview:
    return ExecutionPreview(
        action=IntendedAction(name="x", summary="s", required=frozenset()), allowed=True
    )


def test_the_schema_travels_to_the_provider() -> None:
    """The plan carries it, so a provider that can enforce gets it without anyone wiring."""
    from local_ai_control_center.adapters.mock import MockProvider

    plan = _plan(enforce_shape=True, fields=("claim", "quote"))
    assert plan.output_schema is not None
    # The mock accepts and ignores it, which is the contract for a provider that cannot.
    completion = MockProvider().complete("a prompt", 0.0, plan.output_schema)
    assert completion.text


def test_the_configuration_can_actually_turn_this_on(tmp_path: Path) -> None:
    """Through `plan`, which is the only path the program takes.

    This is the test that was missing. Every other one here builds a `SkillPlan` directly,
    and they all passed while nothing in the program could set `enforce_shape` at all -
    no flag, no configuration key, no declaration. The feature shipped unreachable
    (ADR-055).
    """
    skill = ExtractClaimsSkill()
    asked = Config(workspace_root=tmp_path, enforce_shape=("extract_claims",))
    assert skill.plan(("p.md",), asked).output_schema is not None
    assert skill.plan(("p.md",), Config(workspace_root=tmp_path)).output_schema is None


def test_naming_a_skill_that_answers_in_prose_enforces_nothing(tmp_path: Path) -> None:
    """There is no block shape to enforce, so there is no schema to send.

    By construction rather than by omission: a plan whose whole answer is not the blocks has
    nothing to force into `{entries: [...]}` that would not break the answer.
    """
    plan = SummarizeFileSkill().plan(
        ("p.md",), Config(workspace_root=tmp_path, enforce_shape=("summarize_file",))
    )
    assert plan.enforce_shape, "the configuration named it"
    assert plan.output_schema is None, "and it still gets no schema"


def _shaped(entries: str, closed: bool = True) -> str:
    """A shaped answer, whole or cut off mid-entry the way the engine cuts one."""
    return "{" + NL + Q + "entries" + Q + ": [" + entries + ("]}" if closed else "")


def test_an_answer_cut_short_still_yields_every_entry_that_arrived_whole() -> None:
    """The measurement that forced this: 0 claims from an answer carrying 76 (ADR-056).

    One unclosed brace and `json.loads` returns nothing for the entire document, where the
    line format hands back every complete block before the cut.
    """
    whole = (
        "{"
        + Q
        + "claim"
        + Q
        + ": "
        + Q
        + "first"
        + Q
        + ", "
        + Q
        + "quote"
        + Q
        + ": "
        + Q
        + "the first words"
        + Q
        + "},"
        + "{"
        + Q
        + "claim"
        + Q
        + ": "
        + Q
        + "second"
        + Q
        + ", "
        + Q
        + "quote"
        + Q
        + ": "
        + Q
        + "the second words"
        + Q
        + "},"
    )
    cut = (
        "{"
        + Q
        + "claim"
        + Q
        + ": "
        + Q
        + "third"
        + Q
        + ", "
        + Q
        + "quote"
        + Q
        + ": "
        + Q
        + "the thi"
    )
    claims = parse_claims(_shaped(whole + cut, closed=False))
    assert [c.claim for c in claims] == ["first", "second"], "the cut entry is dropped whole"


def test_recovery_changes_nothing_about_an_answer_that_arrived_whole() -> None:
    """The ordinary path stays the ordinary path: a whole document is parsed as one."""
    body = (
        "{"
        + Q
        + "claim"
        + Q
        + ": "
        + Q
        + "only"
        + Q
        + ", "
        + Q
        + "quote"
        + Q
        + ": "
        + Q
        + "its words"
        + Q
        + "}"
    )
    claims = parse_claims(_shaped(body))
    assert [(c.claim, c.quote) for c in claims] == [("only", "its words")]


def test_a_cut_answer_with_no_whole_entry_falls_back_to_lines() -> None:
    """Nothing recovered must not mean nothing parsed: the line path still runs.

    Enforcement improves a path that works and never replaces it, and that holds for the
    recovery too (ADR-052).
    """
    assert parse_claims(_shaped("{" + Q + "claim" + Q + ": " + Q + "cut immed", closed=False)) == ()


def test_text_that_only_looks_like_json_is_still_read_as_lines() -> None:
    """A model that ignored the schema is parsed the way it always was."""
    claims = parse_claims("CLAIM: a point" + NL + "QUOTE: its words" + NL + "PAGE: 3")
    assert [(c.claim, c.quote, c.page) for c in claims] == [("a point", "its words", 3)]


def test_a_skill_whose_answer_is_prose_and_blocks_cannot_be_enforced(tmp_path: Path) -> None:
    """`assess_source` checks quotations and would still be destroyed by a schema.

    It answers with three headings of prose - what is new, what overlaps, what contradicts -
    and **then** a list of blocks. Forcing that into `{entries: [...]}` deletes the part a
    reader reads, so verifying quotations cannot be the test for whether a shape may be
    enforced (ADR-057).
    """
    plan = AssessSourceSkill().plan(
        ("p.md",), Config(workspace_root=tmp_path, enforce_shape=("assess_source",))
    )
    assert plan.verify_quotes, "it does check its quotations"
    assert not plan.answer_is_entries_only, "and its answer is not only the blocks"
    assert plan.output_schema is None


def test_the_prompt_asks_for_the_shape_the_engine_will_enforce(tmp_path: Path) -> None:
    """The bug this all comes from: the prompt was byte-identical either way.

    A constrained run was told to write `CLAIM:` lines by a prompt while a grammar forbade
    them - an instruction the model could not obey. It never stopped (ADR-057).
    """
    skill = ExtractClaimsSkill()
    asking = skill.plan(("p.md",), Config(workspace_root=tmp_path)).prompt_template
    forcing = skill.plan(
        ("p.md",), Config(workspace_root=tmp_path, enforce_shape=("extract_claims",))
    ).prompt_template

    assert asking != forcing, "the prompt must not be identical whether or not it is enforced"
    assert "CLAIM: what the document asserts" in asking
    assert "CLAIM:" not in forcing, "it cannot ask for a format the grammar forbids"
    assert Q + "entries" + Q in forcing and Q + "claim" + Q in forcing
