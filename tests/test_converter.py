"""Tests for the converter port and its PDF and `.docx` implementations."""

from __future__ import annotations

import zipfile
from collections.abc import Callable
from pathlib import Path

import docx
import pytest

from local_ai_control_center.converter import (
    PAGE_MARKER,
    ConversionError,
    Converter,
    DocxConverter,
    PdfConverter,
    converter_for,
    supported_suffixes,
)


def test_converter_cannot_be_instantiated() -> None:
    """The abstract contract cannot be used directly."""
    with pytest.raises(TypeError):
        Converter()  # type: ignore[abstract]


def test_converter_for_matches_by_suffix(tmp_path: Path) -> None:
    """A source is matched to a converter by what it is, not by the caller choosing."""
    assert isinstance(converter_for(tmp_path / "paper.pdf"), PdfConverter)
    assert isinstance(converter_for(tmp_path / "chapter.docx"), DocxConverter)


def test_converter_for_ignores_suffix_case(tmp_path: Path) -> None:
    """A shouted extension is the same extension."""
    assert isinstance(converter_for(tmp_path / "PAPER.PDF"), PdfConverter)


def test_converter_for_names_what_is_supported(tmp_path: Path) -> None:
    """An unsupported format fails clearly instead of passing bytes through as text."""
    with pytest.raises(ConversionError) as excinfo:
        converter_for(tmp_path / "notes.rtf")
    message = str(excinfo.value)
    assert "notes.rtf" in message
    assert ".pdf" in message and ".docx" in message


def test_supported_suffixes_covers_every_converter() -> None:
    """The list offered in messages is derived from the converters, not written twice."""
    assert supported_suffixes() == frozenset({".pdf", ".docx"})


def test_pdf_text_is_extracted(make_pdf: Callable[..., Path]) -> None:
    """The words in the document come out of it."""
    path = make_pdf("Attention is all you need")
    assert "Attention is all you need" in converter_for(path).extract_text(path)


def test_pdf_marks_page_boundaries(make_pdf: Callable[..., Path]) -> None:
    """Pages are recovered structure: a thesis has to cite them."""
    path = make_pdf("First page", "Second page")
    text = converter_for(path).extract_text(path)
    assert PAGE_MARKER.format(number=1) in text
    assert PAGE_MARKER.format(number=2) in text
    assert text.index("First page") < text.index("Second page")


def test_pdf_page_marker_cannot_be_read_as_a_prompt_fence(make_pdf: Callable[..., Path]) -> None:
    """The marker is an HTML comment, so it can never look like a document fence."""
    path = make_pdf("Some text")
    assert PAGE_MARKER.format(number=1).startswith("<!--")
    assert "<<<" not in converter_for(path).extract_text(path)


def test_pdf_without_a_text_layer_is_reported(make_pdf: Callable[..., Path]) -> None:
    """A scan is named as a scan, and nothing is returned to be written as an empty file."""
    path = make_pdf(" ")
    with pytest.raises(ConversionError) as excinfo:
        converter_for(path).extract_text(path)
    message = str(excinfo.value)
    assert "no extractable text" in message
    assert "OCR" in message


def test_unreadable_pdf_fails_clearly(tmp_path: Path) -> None:
    """A file that is not a PDF fails with a message, not a library traceback."""
    path = tmp_path / "broken.pdf"
    path.write_text("this is not a PDF at all", encoding="utf-8")
    with pytest.raises(ConversionError) as excinfo:
        converter_for(path).extract_text(path)
    assert "broken.pdf" in str(excinfo.value)


def test_missing_pdf_fails_clearly(tmp_path: Path) -> None:
    """A path that is not there is reported, not raised as a bare OSError."""
    with pytest.raises(ConversionError) as excinfo:
        PdfConverter().extract_text(tmp_path / "absent.pdf")
    assert "absent.pdf" in str(excinfo.value)


def test_docx_text_is_extracted(make_docx: Callable[..., Path]) -> None:
    """Body text comes through as body text."""
    path = make_docx((None, "The chapter reviews prior work."))
    assert "The chapter reviews prior work." in converter_for(path).extract_text(path)


def test_docx_heading_levels_come_from_styles(make_docx: Callable[..., Path]) -> None:
    """Headings are recovered from Word's own styles, never guessed from appearance."""
    path = make_docx(
        ("Heading 1", "Theory"),
        ("Heading 2", "Prior work"),
        (None, "Plain paragraph."),
    )
    text = converter_for(path).extract_text(path)
    assert "# Theory" in text
    assert "## Prior work" in text
    assert "\nPlain paragraph." in text


def test_docx_tables_are_flattened_not_dressed_as_markdown(tmp_path: Path) -> None:
    """Cells are real, so they are kept - as rows, not as a table LACC cannot guarantee."""
    path = tmp_path / "tabla.docx"
    document = docx.Document()
    table = document.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Method"
    table.rows[0].cells[1].text = "Error"
    table.rows[1].cells[0].text = "Newton"
    table.rows[1].cells[1].text = "1e-8"
    document.save(str(path))

    text = converter_for(path).extract_text(path)
    assert "Method | Error" in text
    assert "Newton | 1e-8" in text
    assert "---" not in text


def test_empty_docx_is_reported(tmp_path: Path) -> None:
    """An empty document is a failure to report, not an empty file to write."""
    path = tmp_path / "vacio.docx"
    docx.Document().save(str(path))
    with pytest.raises(ConversionError) as excinfo:
        converter_for(path).extract_text(path)
    assert "no extractable text" in str(excinfo.value)


def test_docx_that_is_not_a_docx_fails_clearly(tmp_path: Path) -> None:
    """The older `.doc` format is not this format, and the message says so."""
    path = tmp_path / "viejo.docx"
    path.write_bytes(b"not a zip container at all")
    with pytest.raises(ConversionError) as excinfo:
        converter_for(path).extract_text(path)
    assert ".doc" in str(excinfo.value)


def test_docx_does_not_resolve_external_entities(
    make_docx: Callable[..., Path], tmp_path: Path
) -> None:
    """A `.docx` is untrusted XML: an external entity must not be able to read a file.

    The classic XXE. python-docx does not resolve entities today; this test is here so
    that a change of parser, or of library, cannot quietly reintroduce it.
    """
    secret = tmp_path / "secret.txt"
    secret.write_text("PRIVATE-CONTENT-12345", encoding="utf-8")
    base = make_docx((None, "harmless"), name="base.docx")

    hostile = tmp_path / "xxe.docx"
    document_xml = (
        '<?xml version="1.0"?>\n'
        f'<!DOCTYPE r [<!ENTITY xxe SYSTEM "{secret.as_uri()}">]>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>&xxe;</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(base) as source, zipfile.ZipFile(hostile, "w") as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "word/document.xml":
                data = document_xml.encode("utf-8")
            target.writestr(item, data)

    try:
        text = DocxConverter().extract_text(hostile)
    except ConversionError:
        return  # refusing to parse it at all is also a correct outcome
    assert "PRIVATE-CONTENT" not in text
