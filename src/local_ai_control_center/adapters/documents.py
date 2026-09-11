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
from collections import Counter
from pathlib import Path

from docx import Document
from docx.opc.exceptions import OpcError, PackageNotFoundError
from docx.table import Table
from docx.text.paragraph import Paragraph
from pydantic import BaseModel, ConfigDict
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from local_ai_control_center.ports.converter import ConversionError, Converter

PAGE_MARKER = "<!-- page {number} -->"
"""Marker written where one page of a source document ends and the next begins.

Recovered structure, not invented: the document really does have pages, and work that
cites a source has to name them. An HTML comment renders as nothing in Markdown and
cannot be mistaken for the document fence a prompt uses (ADR-015).
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


_UNREADABLE_SIZE = 4.0
"""Below this a font is not being read by anyone, whatever it is for."""

_INVISIBLE_MODES = (b"3 Tr", b"7 Tr")
"""Rendering modes that draw nothing.

Mode 3 is also what a scanned document's OCR layer uses, over the image a person actually
reads, and that is entirely correct. Which is why this is reported and never judged: the
same operator is proper in a scan and hostile in a typeset paper (ADR-040).
"""


class HiddenText(BaseModel):
    """Text extracted from a document that a reader would not have seen."""

    model_config = ConfigDict(frozen=True)

    reason: str
    page: int
    text: str = ""


def hidden_text_in(reader: PdfReader) -> tuple[HiddenText, ...]:
    """Report the text in a PDF that a reader cannot see, by reason.

    Three signals, each cheap: an invisible rendering mode, a font too small to read, and a
    position outside the page. White-on-white is **not** detected - it needs colour state
    tracked through the content stream - and saying so is part of the decision, because a
    control whose gaps are unlisted is worse than one whose gaps are known (ADR-040).

    All three were tested against PDFs built to hide text, and all three ended up in what
    the extractor returns. That is the point: hidden text reaches the model, and a quotation
    of it passes the grounding check, because it genuinely is in the document.
    """
    found: list[HiddenText] = []
    for number, page in enumerate(reader.pages, start=1):
        try:
            box = page.mediabox
            left, bottom, right, top = (
                float(box.left),
                float(box.bottom),
                float(box.right),
                float(box.top),
            )
        except (AttributeError, TypeError, ValueError):
            left = bottom = 0.0
            right = top = 0.0

        def note(
            text: str,
            cm: object,
            tm: list[float],
            font: object,
            size: float,
            number: int = number,
            bounds: tuple[float, float, float, float] = (left, bottom, right, top),
        ) -> None:
            stripped = text.strip()
            if not stripped:
                return
            if size is not None and 0 <= float(size) < _UNREADABLE_SIZE:
                found.append(HiddenText(reason="too small to read", page=number, text=stripped))
                return
            x0, y0, x1, y1 = bounds
            if x1 > x0 and not (x0 <= tm[4] <= x1 and y0 <= tm[5] <= y1):
                found.append(
                    HiddenText(reason="positioned off the page", page=number, text=stripped)
                )

        try:
            page.extract_text(visitor_text=note)
            contents = page.get_contents()
            raw = contents.get_data() if contents is not None else b""
        except Exception:  # noqa: BLE001 - a malformed page must not stop the report
            continue

        if any(mode in raw for mode in _INVISIBLE_MODES):
            found.append(HiddenText(reason="drawn in an invisible rendering mode", page=number))
    return tuple(found)


class PdfConverter(Converter):
    """Extracts text from a PDF, one page at a time, marking page boundaries.

    Uses pypdf's plain extraction. A multi-column paper will come out worse than a
    layout-aware library would manage; that is accepted for now and is the reversible
    kind of decision this port exists to contain (ADR-016).
    """

    def __init__(self) -> None:
        """Start with nothing dropped and nothing hidden."""
        self._dropped = 0
        self._hidden: tuple[HiddenText, ...] = ()

    @property
    def name(self) -> str:
        """Identify this converter."""
        return "pdf"

    @property
    def furniture_dropped(self) -> int:
        """How many lines the last extraction treated as belonging to the page."""
        return self._dropped

    @property
    def hidden(self) -> tuple[HiddenText, ...]:
        """Text in the last document that a reader would not have seen (ADR-040)."""
        return self._hidden

    @property
    def suffixes(self) -> frozenset[str]:
        """PDFs, and nothing else."""
        return frozenset({".pdf"})

    def extract_text(self, path: Path) -> str:
        """Return the PDF's text with a marker at each page boundary."""
        try:
            reader = PdfReader(path)
            pages = [page.extract_text(extraction_mode="plain") for page in reader.pages]
            self._hidden = hidden_text_in(reader)
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
