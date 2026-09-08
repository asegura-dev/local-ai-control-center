"""Shared fixtures: building the documents the ingestion tests need.

Both PDFs and `.docx` files are built here rather than committed as binary fixtures, so
what a test feeds the converter is visible in the test rather than opaque bytes in the
repository. The PDF is assembled by hand, with its cross-reference offsets computed, to
avoid adding a PDF-writing dependency for the sake of the test suite.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import docx
import pytest


def _minimal_pdf(pages: list[str]) -> bytes:
    """Build a small valid PDF with one line of text per page."""
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",  # placeholder, replaced once the page object numbers are known
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    page_numbers: list[int] = []
    for text in pages:
        page_numbers.append(len(objects) + 1)
        stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Resources "
            b"<< /Font << /F1 3 0 R >> >> /Contents " + str(len(objects) + 2).encode() + b" 0 R >>"
        )
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )
    kids = " ".join(f"{number} 0 R" for number in page_numbers)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode()

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"

    table_start = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{table_start}\n"
    out += trailer.encode() + b"%%EOF\n"
    return bytes(out)


@pytest.fixture
def make_pdf(tmp_path: Path) -> Callable[..., Path]:
    """Return a function that writes a PDF with the given page texts, and its path."""

    def build(*pages: str, name: str = "document.pdf") -> Path:
        path = tmp_path / name
        path.write_bytes(_minimal_pdf(list(pages)))
        return path

    return build


@pytest.fixture
def make_docx(tmp_path: Path) -> Callable[..., Path]:
    """Return a function that writes a `.docx` from (style, text) pairs, and its path."""

    def build(*paragraphs: tuple[str | None, str], name: str = "document.docx") -> Path:
        path = tmp_path / name
        document = docx.Document()
        for style, text in paragraphs:
            document.add_paragraph(text, style=style)
        document.save(str(path))
        return path

    return build
