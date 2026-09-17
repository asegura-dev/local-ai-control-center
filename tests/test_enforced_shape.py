"""A shape the engine enforces, and the path that still works when it cannot (ADR-052)."""

from __future__ import annotations

import json

from local_ai_control_center.core.grounding import parse_claims
from local_ai_control_center.core.preview import ExecutionPreview, IntendedAction
from local_ai_control_center.core.skill import SkillPlan

NL = chr(10)


def _plan(**overrides: object) -> SkillPlan:
    base: dict[str, object] = {
        "action": IntendedAction(name="x", summary="s", required=frozenset()),
        "prompt_template": "t",
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
