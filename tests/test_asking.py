"""Asking a question from the window: what is prepared, and what never raises (ADR-085).

Tk cannot be exercised headlessly, so the section itself is not covered. That is exactly why
everything that decides anything lives outside it - and it is what these tests reach.

The load-bearing ones are the two that assert a **failure comes back as a value**. The window
asks on a worker thread, and an exception crossing a thread boundary into Tk is a window that
stops repainting with nothing on the screen to say why.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from local_ai_control_center.adapters.words import WordRetriever
from local_ai_control_center.core.config import Config
from local_ai_control_center.core.grounding import CheckedClaim, Claim
from local_ai_control_center.core.skill import AskCorpusSkill
from local_ai_control_center.core.workspace import Workspace
from local_ai_control_center.cycle import answer_prepared
from local_ai_control_center.features.ask import (
    Asked,
    Prepared,
    before_preparing,
    prepare,
    ranking_would_send,
    readings_from,
)
from local_ai_control_center.ports.provider import Completion, Provider, ProviderError
from local_ai_control_center.ports.retriever import Outgoing, Passage, Retriever, Selection
from local_ai_control_center.system.audit import AUDIT_FILENAME, AuditLog

CORPUS = """# Collected quotations

Assembled from two documents.

## psma.md

*2 of 2 are in the document.*

### Citable

> The sensitivity for pelvic lymph node metastases was 82 per cent.

p. 4 - verified

Detection sensitivity in the pelvis.

> Nodal staging with PSMA PET outperformed conventional imaging.

p. 7 - verified

Staging comparison.

## dosimetry.md

*1 of 1 are in the document.*

### Citable

> Radiation dosimetry showed an effective dose of 4.4 mSv.

p. 2 - verified

The dose of one scan.
"""

NOTHING_CITABLE = """# Collected quotations

## psma.md

*0 of 1 are in the document.*

### Not in the document

> A sentence the model produced and the document does not hold.

p. 3 - **NOT IN THE DOCUMENT**

An invented reading.
"""

ANSWER = """POINT: PSMA PET detects most pelvic nodal disease.
QUOTE: The sensitivity for pelvic lymph node metastases was 82 per cent.
SOURCE: psma.md

POINT: It is better than what came before.
QUOTE: PSMA PET was superior in every published series.
SOURCE: psma.md
"""


def _config(**over: Any) -> Config:
    settings: dict[str, Any] = {
        "workspace_root": "workspace",
        "model": "qwen2.5:14b",
        "context_tokens": 32_768,
    }
    settings.update(over)
    return Config(**settings)


class _Broken(Retriever):
    """A ranking that fails, which is what an embedding model that is not pulled looks like."""

    @property
    def name(self) -> str:
        return "broken"

    def select(self, question: str, passages: tuple[Passage, ...], budget_tokens: int) -> Selection:
        raise RuntimeError("bge-m3 is not pulled on that host.")

    def would_send(self, passages: tuple[Passage, ...]) -> None:
        return None


class _Meaning(Retriever):
    """A ranking that reaches an engine, and remembers every question it was made to rank."""

    def __init__(self, unembedded: int) -> None:
        self.unembedded = unembedded
        self.ranked: list[str] = []

    @property
    def name(self) -> str:
        return "meaning (a stand-in)"

    def would_send(self, passages: tuple[Passage, ...]) -> Outgoing:
        return Outgoing(model="ollama:bge-m3", unembedded=self.unembedded)

    def select(self, question: str, passages: tuple[Passage, ...], budget_tokens: int) -> Selection:
        self.ranked.append(question)
        return WordRetriever().select(question, passages, budget_tokens)


class _Refuses(Provider):
    """An engine that is not there."""

    @property
    def name(self) -> str:
        return "refuses"

    def complete(
        self, prompt: str, temperature: float = 0.0, schema: dict[str, Any] | None = None
    ) -> Completion:
        raise ProviderError("Cannot reach the engine at http://desk:11434.")


class _Answers(Provider):
    """An engine that quotes one passage correctly and invents the other."""

    @property
    def name(self) -> str:
        return "answers"

    def complete(
        self, prompt: str, temperature: float = 0.0, schema: dict[str, Any] | None = None
    ) -> Completion:
        return Completion(text=ANSWER, provider="answers")


# --- what is prepared, before anything is sent ---------------------------------------------


def test_a_question_that_is_only_whitespace_is_refused_rather_than_ranked() -> None:
    made = prepare("   \n  ", "corpus.md", CORPUS, _config(), WordRetriever())
    assert not made.sendable
    assert made.refusal
    assert not made.material


def test_without_a_context_window_there_is_no_budget_to_select_against() -> None:
    """The same refusal `lacc ask` gives, for the same reason."""
    config = _config(context_tokens=None)
    made = prepare("lymph node", "corpus.md", CORPUS, config, WordRetriever())
    assert not made.sendable
    assert "context_tokens" in made.refusal


def test_a_corpus_of_nothing_but_invented_quotations_has_nothing_to_ask_from() -> None:
    """Only what was found in its document is eligible, which is the rule `ask` keeps."""
    made = prepare("invented", "corpus.md", NOTHING_CITABLE, _config(), WordRetriever())
    assert not made.sendable
    assert "no quotation that was found" in made.refusal


def test_a_question_matching_nothing_says_so_and_offers_no_way_to_send_it() -> None:
    made = prepare("chromodynamics", "corpus.md", CORPUS, _config(), WordRetriever())
    assert not made.sendable
    assert made.considered == 3
    assert "does not find quotations in another" in made.refusal
    assert "an embedding model, configured, would cross them" in made.refusal


def test_with_a_model_configured_the_refusal_names_the_no_that_was_said() -> None:
    """It said "unless an embedding model is configured" of one that was (ADR-117)."""
    configured = _config().model_copy(update={"embedding_model": "bge-m3"})
    made = prepare("chromodynamics", "corpus.md", CORPUS, configured, WordRetriever())
    assert "say yes to ranking by meaning" in made.refusal
    assert "is configured" not in made.refusal


def test_a_ranking_that_fails_becomes_a_sentence_rather_than_an_exception() -> None:
    """It runs where a traceback has nowhere to go. A refusal is the only safe shape."""
    made = prepare("lymph node", "corpus.md", CORPUS, _config(), _Broken())
    assert not made.sendable
    assert "bge-m3" in made.refusal


def test_what_would_be_sent_is_counted_completely() -> None:
    """Selected plus set aside is everything, so a preview cannot hide a discard."""
    made = prepare("pelvic lymph node sensitivity", "corpus.md", CORPUS, _config(), WordRetriever())
    assert made.sendable
    assert made.considered == 3
    assert made.selected + made.set_aside == made.considered
    assert made.tokens > 0
    assert made.how
    assert "82 per cent" in made.material
    assert made.model == "qwen2.5:14b"


def test_the_preview_says_nothing_leaves_the_machine_when_the_network_is_off() -> None:
    made = prepare("pelvic lymph node", "corpus.md", CORPUS, _config(), WordRetriever())
    assert made.reaches == "this machine only"


def test_the_preview_names_the_host_it_would_reach_when_the_network_is_on() -> None:
    config = _config(network_access=True, engine_host="http://desk:11434")
    made = prepare("pelvic lymph node", "corpus.md", CORPUS, config, WordRetriever())
    assert "desk" in made.reaches


# --- what a ranking may send, before it sends anything (ADR-106) ----------------------------


def test_a_ranking_that_reaches_the_engine_waits_for_somebody_to_agree() -> None:
    """The question used to be embedded before the preview that asked whether to send it."""
    meaning = _Meaning(unembedded=0)
    config = _config(network_access=True, engine_host="http://desk:11434")
    made = prepare("pelvic lymph node", "corpus.md", CORPUS, config, meaning)
    assert meaning.ranked == [], "nothing was ranked, so nothing was sent"
    assert not made.sendable
    assert made.awaiting is not None
    assert "your question" in made.asks
    assert "ollama:bge-m3" in made.asks
    assert "desk" in made.asks


def test_agreeing_to_the_question_alone_ranks_when_nothing_else_would_go() -> None:
    meaning = _Meaning(unembedded=0)
    made = prepare("pelvic lymph node", "corpus.md", CORPUS, _config(), meaning, agreed=0)
    assert meaning.ranked == ["pelvic lymph node"]
    assert made.sendable
    assert made.awaiting is None


def test_the_question_alone_does_not_cover_quotations_never_embedded() -> None:
    """A press of Prepare agrees to the question. A corpus's worth of quotations is more."""
    meaning = _Meaning(unembedded=3)
    made = prepare("pelvic lymph node", "corpus.md", CORPUS, _config(), meaning, agreed=0)
    assert meaning.ranked == []
    assert made.awaiting is not None
    assert made.awaiting.unembedded == 3
    assert "your question and 3 quotations never embedded before" in made.asks


def test_agreement_covers_what_was_shown_and_not_more() -> None:
    """Two were shown and the corpus grew to three before the press: three are asked about."""
    meaning = _Meaning(unembedded=3)
    shown_fewer = prepare("pelvic lymph node", "corpus.md", CORPUS, _config(), meaning, agreed=2)
    assert meaning.ranked == []
    assert shown_fewer.awaiting is not None
    shown_all = prepare("pelvic lymph node", "corpus.md", CORPUS, _config(), meaning, agreed=3)
    assert shown_all.sendable


def test_ranking_by_words_needs_no_agreement() -> None:
    """It never leaves this machine, so there is nothing to agree to."""
    made = prepare("pelvic lymph node", "corpus.md", CORPUS, _config(), WordRetriever())
    assert made.awaiting is None
    assert made.asks == ""
    assert made.sendable


def test_one_quotation_is_counted_in_the_singular() -> None:
    sentence = ranking_would_send(Outgoing(model="m", unembedded=1), "this machine only")
    assert "your question and 1 quotation never embedded before to m" in sentence


class _MeaningGoesAway(_Meaning):
    """A ranking that reaches for the engine and finds nothing there."""

    def select(self, question: str, passages: tuple[Passage, ...], budget_tokens: int) -> Selection:
        raise RuntimeError("Cannot reach http://desk:11434 to embed")


def test_what_a_ranking_sent_comes_back_with_the_prepared_question() -> None:
    """So the terminal and the window record the same thing from the same value (ADR-108)."""
    made = prepare("pelvic lymph node", "corpus.md", CORPUS, _config(), _Meaning(2), agreed=2)
    assert made.ranked is not None
    assert made.ranked.sent == Outgoing(model="ollama:bge-m3", unembedded=2)
    assert made.ranked.failed == ""


def test_a_ranking_that_did_not_come_back_still_says_what_it_reached_for() -> None:
    made = prepare("lymph node", "corpus.md", CORPUS, _config(), _MeaningGoesAway(0), agreed=0)
    assert made.refusal
    assert made.ranked is not None
    assert "Cannot reach" in made.ranked.failed


def test_nothing_ranked_is_nothing_to_record() -> None:
    """Waiting for agreement, or ranking by words: nothing left the machine."""
    waiting = prepare("pelvic lymph node", "corpus.md", CORPUS, _config(), _Meaning(0))
    by_words = prepare("pelvic lymph node", "corpus.md", CORPUS, _config(), WordRetriever())
    assert waiting.ranked is None
    assert by_words.ranked is None


def test_the_line_beside_prepare_names_what_pressing_it_sends() -> None:
    """The preview of what Prepare sends, drawn before it is pressed."""
    config = _config(embedding_model="bge-m3", network_access=True, engine_host="http://desk:11434")
    line = before_preparing(config)
    assert "your question" in line
    assert "bge-m3" in line
    assert "desk" in line
    words_only = before_preparing(_config())
    assert "on this machine" in words_only
    assert "bge-m3" not in words_only


# --- what comes back ------------------------------------------------------------------------


def test_a_reading_carries_whether_its_quotation_was_in_what_was_shown() -> None:
    checked = (
        CheckedClaim(
            claim=Claim(claim="a reading", quote="words that are there"),
            verdict="verified",
        ),
        CheckedClaim(
            claim=Claim(claim="another", quote="words that are not"),
            verdict="not_found",
            nearest="something close",
        ),
    )
    readings = readings_from(checked)
    assert [r.found for r in readings] == [True, False]
    assert readings[1].nearest == "something close"


def test_a_failure_is_a_result_with_a_sentence_in_it() -> None:
    answered = Asked(prepared=Prepared(question="x"), failure="the engine is not there")
    assert not answered.worked
    assert not answered.answer


def _sent(root: Path, provider: Provider) -> Asked:
    root.mkdir(parents=True, exist_ok=True)
    config = _config(workspace_root=str(root))
    workspace = Workspace(root=root)
    made = prepare("pelvic lymph node sensitivity", "corpus.md", CORPUS, config, WordRetriever())
    assert made.sendable
    skill = AskCorpusSkill()
    return answer_prepared(
        made,
        skill,
        skill.plan((made.question,), config),
        config,
        workspace,
        provider,
        AuditLog(workspace, config),
        "run-for-the-test",
    )


def test_an_engine_that_is_not_there_comes_back_as_a_value_not_a_raise(tmp_path: Path) -> None:
    """The one that matters. The caller is a worker thread with no way to report a raise."""
    answered = _sent(tmp_path / "away", _Refuses())
    assert not answered.worked
    assert "Cannot reach the engine" in answered.failure


def test_an_answer_carries_its_quotations_checked_against_what_was_sent(tmp_path: Path) -> None:
    """Against the passages, not the documents: those were checked when the corpus was built."""
    answered = _sent(tmp_path / "good", _Answers())
    assert answered.worked
    assert len(answered.readings) == 2
    assert answered.invented == 1
    invented = [r for r in answered.readings if not r.found]
    assert "superior in every published series" in invented[0].quote


def test_the_run_is_recorded_whichever_way_it_went(tmp_path: Path) -> None:
    """A question asked from the window is audited exactly as one asked from a terminal."""
    root = tmp_path / "audited"
    _sent(root, _Refuses())
    written = (root / AUDIT_FILENAME).read_text(encoding="utf-8")
    assert "passages_selected" in written


def test_under_the_default_level_a_question_is_kept_only_as_its_digest(tmp_path: Path) -> None:
    """A question is content. Under `standard` it was kept word for word, because nothing had
    told the filter so (ADR-105)."""
    root = tmp_path / "private"
    _sent(root, _Refuses())
    written = (root / AUDIT_FILENAME).read_text(encoding="utf-8")
    assert "pelvic lymph node sensitivity" not in written
    assert "question_sha256" in written
