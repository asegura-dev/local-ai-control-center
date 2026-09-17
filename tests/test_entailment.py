"""Judging whether a reading follows from its words (ADR-053).

The judge itself is graded against `fixtures/seeded/readings.yaml`, whose labels were written
by a person before anything ran. That grading needs an engine and is not part of this suite;
these tests cover the machinery around it - that a failure costs one pair, that an
unparseable answer is not silently an approval, and that `undecided` is never `supported`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from local_ai_control_center.adapters.asking import AskingJudge
from local_ai_control_center.ports.entailment import Judgement
from local_ai_control_center.ports.provider import Completion, Provider

_SEEDED = Path(__file__).parent / "fixtures" / "seeded" / "readings.yaml"


class _Answers(Provider):
    """A provider that returns whatever it was handed, or raises."""

    def __init__(self, text: str = "", explode: bool = False) -> None:
        self._text = text
        self._explode = explode
        self.schemas: list[Any] = []

    @property
    def name(self) -> str:
        return "answers"

    def complete(
        self, prompt: str, temperature: float = 0.0, schema: dict[str, Any] | None = None
    ) -> Completion:
        if self._explode:
            raise RuntimeError("the engine is down")
        self.schemas.append(schema)
        return Completion(text=self._text, provider=self.name)


def _said(verdict: str, why: str = "because") -> str:
    return json.dumps({"verdict": verdict, "why": why})


@pytest.mark.parametrize("verdict", ["follows", "contradicts", "neither"])
def test_each_verdict_is_carried_back(verdict: str) -> None:
    judged = AskingJudge(_Answers(_said(verdict))).judge("a claim", "a quotation")
    assert judged.verdict == verdict
    assert judged.detail == "because"


def test_only_follows_counts_as_supported() -> None:
    """`undecided` is not approval. A judge that could not answer has not said it is fine."""
    for verdict in ("contradicts", "neither", "undecided"):
        assert not Judgement(verdict=verdict).supported  # type: ignore[arg-type]
    assert Judgement(verdict="follows").supported


def test_the_two_that_need_a_person_are_named() -> None:
    assert Judgement(verdict="contradicts").worth_a_look
    assert Judgement(verdict="neither").worth_a_look
    assert not Judgement(verdict="follows").worth_a_look
    assert not Judgement(verdict="undecided").worth_a_look, "a failed judge is not a finding"


def test_an_engine_that_is_down_costs_one_pair_and_not_the_traverse() -> None:
    judged = AskingJudge(_Answers(explode=True)).judge("a claim", "a quotation")
    assert judged.verdict == "undecided"
    assert "could not answer" in judged.detail


def test_an_answer_out_of_shape_is_undecided_rather_than_approval() -> None:
    judged = AskingJudge(_Answers("I think it probably follows, yes")).judge("c", "q")
    assert judged.verdict == "undecided"
    assert not judged.supported


def test_a_verdict_nobody_asked_for_is_refused() -> None:
    judged = AskingJudge(_Answers(_said("probably"))).judge("c", "q")
    assert judged.verdict == "undecided"
    assert "probably" in judged.detail


def test_nothing_to_judge_is_not_a_judgement() -> None:
    judge = AskingJudge(_Answers(_said("follows")))
    assert judge.judge("", "a quotation").verdict == "undecided"
    assert judge.judge("a claim", "   ").verdict == "undecided"


def test_the_shape_is_enforced_so_the_answer_can_only_be_a_label() -> None:
    provider = _Answers(_said("follows"))
    AskingJudge(provider).judge("a claim", "a quotation")
    schema = provider.schemas[0]
    assert schema is not None
    assert schema["properties"]["verdict"]["enum"] == ["follows", "contradicts", "neither"]


def test_the_judge_names_the_model_behind_it() -> None:
    """A record should say who judged, not only that something did."""
    assert AskingJudge(_Answers()).name == "asking:answers"


def test_the_fixture_that_grades_the_judge_holds_all_three_labels() -> None:
    """A fixture with only easy labels would grade nothing. `neither` is the hard one."""
    loaded = yaml.safe_load(_SEEDED.read_text(encoding="utf-8"))
    verdicts = [pair["verdict"] for pair in loaded["pairs"]]
    assert set(verdicts) == {"follows", "contradicts", "neither"}
    assert verdicts.count("neither") >= 3, "the label that matters needs more than one case"
    assert all(pair["quotation"].strip() and pair["claim"].strip() for pair in loaded["pairs"])


def test_the_real_case_is_the_first_seed() -> None:
    """The pair that made this port exist: a verified quotation about choline, read as PSMA."""
    loaded = yaml.safe_load(_SEEDED.read_text(encoding="utf-8"))
    first = loaded["pairs"][0]
    assert first["verdict"] == "neither"
    assert "choline" in first["quotation"]
    assert "PSMA" in first["claim"]
