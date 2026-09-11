"""Shared fixtures, and the guard that keeps LACC from reaching the network.

The egress guard is the important half. "LACC does not use the network" was an assertion
in a document until v0.21.0; here it becomes something the quality gate enforces, so a
dependency, a future feature or a careless import that reaches outward fails the build
rather than shipping (ADR-022).

The rest of this file builds the documents the ingestion tests need.

Both PDFs and `.docx` files are built here rather than committed as binary fixtures, so
what a test feeds the converter is visible in the test rather than opaque bytes in the
repository. The PDF is assembled by hand, with its cross-reference offsets computed, to
avoid adding a PDF-writing dependency for the sake of the test suite.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterator
from pathlib import Path

import docx
import pytest

_real_connect = socket.socket.connect


def _is_loopback(host: object) -> bool:
    """Whether ``host`` names this machine. Anything unrecognised is not loopback."""
    if not isinstance(host, str):
        return False
    if host.lower() in ("localhost", "::1"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True, scope="session")
def _no_egress() -> Iterator[None]:
    """Fail any test that opens a connection to something other than this machine.

    Autouse and session-scoped, so it covers the suite rather than the tests that
    remember to ask for it. Loopback stays allowed: talking to a local engine is
    inter-process communication, and PRINCIPLES treats it as the one exception.
    """

    def guarded(self: socket.socket, address: object) -> object:
        host = address[0] if isinstance(address, tuple) else None
        if not _is_loopback(host):
            raise AssertionError(
                f"LACC tried to reach {address!r}, which is not this machine. Nothing in "
                "LACC may leave the machine; if this is a new dependency doing it, the "
                "dependency is the problem (ADR-022)."
            )
        return _real_connect(self, address)

    socket.socket.connect = guarded  # type: ignore[method-assign]
    try:
        yield
    finally:
        socket.socket.connect = _real_connect  # type: ignore[method-assign]


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


def pdf_with_streams(streams: list[str]) -> bytes:
    """Build a PDF whose page content streams are given verbatim.

    Lets a test hide text the way a hostile document would - an invisible rendering mode,
    a font too small to read, a position off the page - rather than describing it (ADR-040).
    """
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    page_numbers: list[int] = []
    for stream in streams:
        page_numbers.append(len(objects) + 1)
        body = stream.encode()
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Resources "
            b"<< /Font << /F1 3 0 R >> >> /Contents " + str(len(objects) + 2).encode() + b" 0 R >>"
        )
        objects.append(
            b"<< /Length " + str(len(body)).encode() + b" >>\nstream\n" + body + b"\nendstream"
        )
    kids = " ".join(f"{number} 0 R" for number in page_numbers)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(streams)} >>".encode()

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    table_start = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{table_start}\n"
    ).encode() + b"%%EOF\n"
    return bytes(out)
