"""Converters: turning a document into text LACC can read.

LACC reads UTF-8 text and refuses anything else (ADR-014), while the material real work
arrives in is PDF and `.docx`. `Converter` is the port that closes that gap: an abstract
contract with one operation, mirroring the provider port, shaped by two concrete
implementations from the start rather than guessed from one (ADR-016).

What comes out is extracted text, not a faithful rendering. Structure that can be
detected is kept - a page boundary, a heading style - and structure that cannot be is not
invented. Conversion is deliberately a step that produces a file the user can open and
correct, rather than a parse hidden inside a read.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections import Counter
from pathlib import Path

from docx import Document
from docx.opc.exceptions import OpcError, PackageNotFoundError
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader
from pypdf.errors import PyPdfError

PAGE_MARKER = "<!-- page {number} -->"
"""Marker written where one page of a source document ends and the next begins.

Recovered structure, not invented: the document really does have pages, and work that
cites a source has to name them. An HTML comment renders as nothing in Markdown and
cannot be mistaken for the document fence a prompt uses (ADR-015).
"""


class ConversionError(Exception):
    """Raised when a document cannot be turned into text.

    Carries a message already translated into something a person can act on, the same
    posture `ProviderError` and `ReadError` take: a failure at an external, volatile
    boundary is reported clearly, never surfaced as a library's own error.
    """


class Converter(ABC):
    """Abstract port for anything that extracts text from a document.

    Implementations declare which file suffixes they handle, so a source is matched to
    a converter by what it is rather than by the caller knowing which to pick.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier of the converter, for audit records and messages."""

    @property
    @abstractmethod
    def suffixes(self) -> frozenset[str]:
        """Lower-case file suffixes this converter handles, including the dot."""

    @abstractmethod
    def extract_text(self, path: Path) -> str:
        """Return the text of the document at ``path``.

        Raises :class:`ConversionError` when the document cannot be read, or when it
        holds no extractable text at all - an empty result is reported, never returned.
        """


_DIGITS = re.compile(r"\d+")


def _shape_of(line: str) -> str:
    """The line with digit runs replaced, so a page number does not make it unique.

    A running header carries the page number glued to it, so `3413European Journal...` and
    `3417European Journal...` are different strings and counting repeats finds nothing.
    Comparing shapes finds them (ADR-036).
    """
    return _DIGITS.sub("#", line.strip())


def furniture_in(pages: list[str]) -> frozenset[str]:
    """Return the shapes of lines belonging to the page rather than to the text.

    A shape on at least half the pages is a running header, a footer or a page number; one
    on a single page of seven is content. Never fewer than two pages, because with a short
    document "half" is not evidence of anything.
    """
    if len(pages) < 2:
        return frozenset()
    seen: Counter[str] = Counter()
    for page in pages:
        seen.update({_shape_of(line) for line in page.splitlines() if line.strip()})
    threshold = max(2, len(pages) // 2)
    return frozenset(shape for shape, count in seen.items() if count >= threshold)


def without_furniture(pages: list[str]) -> tuple[list[str], int]:
    """Drop the furniture from each page, and report how many lines went.

    The count is returned rather than discarded. A heuristic that quietly deletes text from
    a document the user keeps is the wrong shape for this project, and an ingestion that
    dropped an implausible amount should be visible afterwards (ADR-036).
    """
    shapes = furniture_in(pages)
    if not shapes:
        return pages, 0

    kept, dropped = [], 0
    for page in pages:
        lines = []
        for line in page.splitlines():
            if line.strip() and _shape_of(line) in shapes:
                dropped += 1
                continue
            lines.append(line)
        kept.append("\n".join(lines))
    return kept, dropped


class PdfConverter(Converter):
    """Extracts text from a PDF, one page at a time, marking page boundaries.

    Uses pypdf's plain extraction. A multi-column paper will come out worse than a
    layout-aware library would manage; that is accepted for now and is the reversible
    kind of decision this port exists to contain (ADR-016).
    """

    def __init__(self) -> None:
        """Start with nothing dropped."""
        self._dropped = 0

    @property
    def name(self) -> str:
        """Identify this converter."""
        return "pdf"

    @property
    def furniture_dropped(self) -> int:
        """How many lines the last extraction treated as belonging to the page."""
        return self._dropped

    @property
    def suffixes(self) -> frozenset[str]:
        """PDFs, and nothing else."""
        return frozenset({".pdf"})

    def extract_text(self, path: Path) -> str:
        """Return the PDF's text with a marker at each page boundary."""
        try:
            reader = PdfReader(path)
            pages = [page.extract_text(extraction_mode="plain") for page in reader.pages]
        except PyPdfError as error:
            raise ConversionError(f"Cannot read {path.name} as a PDF: {error}") from error
        except OSError as error:
            raise ConversionError(f"Cannot open {path.name}: {error.strerror or error}.") from error

        pages, self._dropped = without_furniture(pages)
        blocks = [
            f"{PAGE_MARKER.format(number=number)}\n\n{text.strip()}"
            for number, text in enumerate(pages, start=1)
            if text.strip()
        ]
        if not blocks:
            raise ConversionError(
                f"{path.name} has no extractable text. It is most likely a scan, an image "
                "of a document rather than a document. Recognising text in images (OCR) is "
                "outside what LACC does."
            )
        return "\n\n".join(blocks) + "\n"


class DocxConverter(Converter):
    """Extracts text from a `.docx`, keeping heading levels and table rows in order.

    Heading levels are recovered rather than invented: a Word heading style says what it
    is. Tables are flattened to one line per row - their cells are real, but rendering
    them as a Markdown table would claim a fidelity that merged cells break.
    """

    @property
    def name(self) -> str:
        """Identify this converter."""
        return "docx"

    @property
    def suffixes(self) -> frozenset[str]:
        """Word documents in the Open XML format. The older `.doc` is not this format."""
        return frozenset({".docx"})

    def extract_text(self, path: Path) -> str:
        """Return the document's text, in document order, headings and tables included."""
        try:
            document = Document(str(path))
            blocks = [_render(item) for item in document.iter_inner_content()]
        except (OpcError, PackageNotFoundError) as error:
            raise ConversionError(
                f"Cannot read {path.name} as a Word document: {error}. The older `.doc` "
                "format is not `.docx` and is not supported."
            ) from error
        except OSError as error:
            raise ConversionError(f"Cannot open {path.name}: {error.strerror or error}.") from error

        kept = [block for block in blocks if block]
        if not kept:
            raise ConversionError(f"{path.name} has no extractable text: it is empty.")
        return "\n\n".join(kept) + "\n"


def _render(item: Paragraph | Table) -> str:
    """Turn one piece of a Word document into text, or into nothing if it is empty."""
    if isinstance(item, Table):
        rows = [
            " | ".join(cell.text.strip() for cell in row.cells)
            for row in item.rows
            if any(cell.text.strip() for cell in row.cells)
        ]
        return "\n".join(rows)

    text = item.text.strip()
    if not text:
        return ""
    level = _heading_level(item)
    return f"{'#' * level} {text}" if level else text


def _heading_level(paragraph: Paragraph) -> int:
    """Return the Markdown heading level a paragraph's style implies, or 0 for none.

    Word names its heading styles "Heading 1" through "Heading 9". Anything else is body
    text: no level is guessed from how a paragraph looks.
    """
    style = paragraph.style
    name = style.name if style is not None else None
    if name is None or not name.startswith("Heading "):
        return 0
    number = name.removeprefix("Heading ")
    return int(number) if number.isdigit() and 1 <= int(number) <= 9 else 0


CONVERTERS: tuple[Converter, ...] = (PdfConverter(), DocxConverter())
"""The converters LACC has. A closed set that grows when a real format needs it."""


def supported_suffixes() -> frozenset[str]:
    """Every suffix any converter handles, for error messages and help text."""
    return frozenset().union(*(converter.suffixes for converter in CONVERTERS))


def converter_for(path: Path) -> Converter:
    """Return the converter that handles ``path``, chosen by its suffix.

    An unsupported suffix is a clear error naming what is supported, rather than a
    silent pass-through that would write the bytes of a binary into a text file.
    """
    suffix = path.suffix.lower()
    for converter in CONVERTERS:
        if suffix in converter.suffixes:
            return converter
    supported = ", ".join(sorted(supported_suffixes()))
    raise ConversionError(
        f"LACC does not know how to convert {path.name}. Supported formats: {supported}."
    )
