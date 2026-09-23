"""Which work a document is, when nothing in it says so (ADR-087).

The measurement behind this module is that **no test separated a document's own printed DOI
from one it cites**, so what is tested here is that nothing pretends to: the candidates come
back in the order they were printed, with no verdict attached, and the answer is whatever a
person wrote down beside the file.
"""

from __future__ import annotations

from pathlib import Path

from local_ai_control_center.features.identity import (
    DOI_BESIDE,
    beside,
    establish,
    established_for,
    opening_of,
    printed_dois,
)

OWN_AND_CITED = """<!-- page 1 -->
Statistics at a glance, 2022
Top 5 most frequent cancers

Sources: Sung H, et al. Global cancer statistics 2020. https://doi.org/10.3322/caac.21660.
Ferlay J, et al. Cancer statistics for the year 2020. https://doi.org/10.1002/ijc.33588.
"""

ONE_DOI_TWICE = """<!-- page 1 -->
https://doi.org/10.1177/17562872221128791
Ther Adv Urol 2022, Vol. 14: 1-31
A review of artificial intelligence in prostate cancer detection
DOI: 10.1177/17562872221128791
"""


def test_the_candidates_come_back_in_the_order_they_were_printed() -> None:
    found = printed_dois(OWN_AND_CITED)
    assert found == ("10.3322/caac.21660", "10.1002/ijc.33588")


def test_a_document_that_prints_only_what_it_cites_looks_exactly_like_one_that_does_not() -> None:
    """The measured finding, held as a test so nobody adds a verdict here by accident.

    Both DOIs above belong to works this document cites. Nothing in this module can tell,
    which is why `identify` shows them and chooses none of them.
    """
    assert len(printed_dois(OWN_AND_CITED)) == 2


def test_the_same_doi_printed_twice_is_one_candidate() -> None:
    assert printed_dois(ONE_DOI_TWICE) == ("10.1177/17562872221128791",)


def test_a_doi_printed_at_the_end_of_a_sentence_loses_the_full_stop() -> None:
    """`caac.21660.` with the sentence's period stuck to it is not a DOI the registry holds.

    Only the trailing one: a DOI's own suffix is full of dots, and cutting those would ask
    about a different work (ADR-083).
    """
    found = printed_dois("see https://doi.org/10.3322/caac.21660.")
    assert found == ("10.3322/caac.21660",)


def test_only_the_front_matter_is_looked_at() -> None:
    """Past the front, every DOI belongs to the reference list."""
    buried = "x" * 7000 + " 10.1234/buried"
    assert printed_dois(buried) == ()


def test_the_opening_leaves_out_the_page_markers_lacc_added() -> None:
    """They are LACC's, not the document's, and this line exists to show the document."""
    said = opening_of(ONE_DOI_TWICE)
    assert "page 1" not in said
    assert said.startswith("https://doi.org/10.1177")


def test_what_was_established_is_kept_beside_the_file_never_inside_it(tmp_path: Path) -> None:
    """Hundreds of quotations are checked against these documents as they are."""
    document = tmp_path / "paper.md"
    document.write_text("the paper, unchanged", encoding="utf-8")
    written = establish(document, "10.2967/jnumed.119.234187", "Head-to-Head Comparison")
    assert written == beside(document)
    assert written.name.endswith(DOI_BESIDE)
    assert document.read_text(encoding="utf-8") == "the paper, unchanged"


def test_an_established_doi_is_read_back_with_what_the_registry_said(tmp_path: Path) -> None:
    document = tmp_path / "paper.md"
    document.write_text("anything", encoding="utf-8")
    establish(document, "10.2967/jnumed.119.234187", "Head-to-Head Comparison", when="2026-09-23")
    held = established_for(document)
    assert held is not None
    assert held.doi == "10.2967/jnumed.119.234187"
    assert held.title == "Head-to-Head Comparison"
    assert held.established == "2026-09-23"


def test_a_document_with_nothing_established_says_nothing(tmp_path: Path) -> None:
    document = tmp_path / "paper.md"
    document.write_text("anything", encoding="utf-8")
    assert established_for(document) is None


def test_an_unreadable_note_does_not_stop_the_document_being_used(tmp_path: Path) -> None:
    """A broken fact *about* a file must not take the file down with it."""
    document = tmp_path / "paper.md"
    document.write_text("anything", encoding="utf-8")
    beside(document).write_text("{ this is not json", encoding="utf-8")
    assert established_for(document) is None


def test_a_note_holding_no_doi_is_nothing_rather_than_an_empty_answer(tmp_path: Path) -> None:
    document = tmp_path / "paper.md"
    document.write_text("anything", encoding="utf-8")
    beside(document).write_text('{"title": "something"}', encoding="utf-8")
    assert established_for(document) is None
