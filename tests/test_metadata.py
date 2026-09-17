"""What a document says about itself, and what it does not (ADR-047)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfWriter

from local_ai_control_center.adapters.documents import embedded_metadata
from local_ai_control_center.core.headings import DocumentMetadata, normalized_doi


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("10.1007/s00259-016-3573-4", "10.1007/s00259-016-3573-4"),
        ("doi:10.1038/s41592-020-01008-z", "10.1038/s41592-020-01008-z"),
        ("https://doi.org/10.1007/s10278-024-01104-y", "10.1007/s10278-024-01104-y"),
        ("DOI: 10.1111/bju.16412", "10.1111/bju.16412"),
        ("  10.1016/j.compbiomed.2023.106882  ", "10.1016/j.compbiomed.2023.106882"),
    ],
)
def test_the_three_ways_a_doi_is_written_give_one_identifier(written: str, expected: str) -> None:
    """All five spellings appear in one real bibliography."""
    assert normalized_doi(written) == expected


@pytest.mark.parametrize("nonsense", ["", "not a doi", "arXiv:1610.02391", "10", "https://x.y"])
def test_something_that_is_not_a_doi_is_not_reported_as_one(nonsense: str) -> None:
    """Better empty than a plausible identifier, which is what this whole area is about."""
    assert normalized_doi(nonsense) == ""


def test_an_empty_record_names_everything_it_is_missing() -> None:
    empty = DocumentMetadata()
    assert not empty.says_anything
    assert empty.missing == ("title", "authors", "DOI", "date")


def test_a_partial_record_names_only_what_is_absent() -> None:
    partial = DocumentMetadata(title="A paper", doi="10.1/x")
    assert partial.says_anything
    assert partial.missing == ("authors", "date")


def _pdf(path: Path, **info: str) -> Path:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    if info:
        writer.add_metadata({f"/{key}": value for key, value in info.items()})
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def test_a_title_and_authors_are_read_from_the_file(tmp_path: Path) -> None:
    path = _pdf(tmp_path / "paper.pdf", Title="A Paper", Author="Ada Lovelace; Alan Turing")
    found = embedded_metadata(path)
    assert found.title == "A Paper"
    assert found.authors == ("Ada Lovelace", "Alan Turing")


def test_a_file_that_says_nothing_says_nothing(tmp_path: Path) -> None:
    """Five of twenty-three real papers give this answer, and it is an answer."""
    found = embedded_metadata(_pdf(tmp_path / "silent.pdf"))
    assert not found.says_anything
    assert found.missing == ("title", "authors", "DOI", "date")


def test_a_file_that_cannot_be_read_reports_nothing_rather_than_raising(tmp_path: Path) -> None:
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"this is not a PDF at all")
    assert embedded_metadata(broken) == DocumentMetadata()
    assert embedded_metadata(tmp_path / "absent.pdf") == DocumentMetadata()


def test_the_journal_is_never_reported(tmp_path: Path) -> None:
    """Measured: the embedded field names the publisher in ten of eleven files.

    `Springer US` reported as a journal would be a plausible wrong answer, which is the
    failure this replaces rather than repeats (ADR-047).
    """
    path = _pdf(tmp_path / "paper.pdf", Title="A Paper")
    assert not hasattr(embedded_metadata(path), "journal")
