"""What a file in a workspace is, decided once (ADR-090).

Every kind is pinned against a file that opens the way its writer opens it, so a writer that
changes its first line fails here rather than in somebody's workspace.

The last test is the one that matters: **nothing outside `core.kinds` may decide this
again.** Two slices did, they drifted nine files apart, and nothing caught it - the layering
rule checks where code lives, not whether the same decision is made twice in the right place.
"""

from __future__ import annotations

import ast
import pathlib
from pathlib import Path

from local_ai_control_center.core.kinds import WRITTEN_BY_LACC, kind_of

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "src" / "local_ai_control_center"


def _written(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_both_openings_a_corpus_is_written_with_are_a_corpus(tmp_path: Path) -> None:
    """`collect` and `corpus` write different first lines and both mean the same thing."""
    assert kind_of(_written(tmp_path, "a.md", "# Collected quotations\n\n> a\n")) == "corpus"
    assert kind_of(_written(tmp_path, "b.md", "# Claims collected by x\n\n> a\n")) == "corpus"


def test_what_lacc_writes_is_recognised_and_grouped(tmp_path: Path) -> None:
    kinds = {
        "bibliography": "# Bibliography\n\n11 works resolved.\n",
        "review": "# Review of draft.md\n\nagainst corpus.md\n",
        "coverage": "# How far the nearest quotation is\n\n3 topics.\n",
    }
    for kind, text in kinds.items():
        assert kind_of(_written(tmp_path, f"{kind}.md", text)) == kind
        assert kind in WRITTEN_BY_LACC


def test_a_section_taken_out_of_a_document_opens_with_its_number(tmp_path: Path) -> None:
    """It is neither a document somebody brought nor something LACC wrote about one."""
    assert kind_of(_written(tmp_path, "s.md", "6.3 Treatment by stage\n\ntext\n")) == "extract"
    assert kind_of(_written(tmp_path, "t.md", "5.2.4\nImaging\n")) == "extract"


def test_a_topics_file_is_recognised_by_the_marker_coverage_demands(tmp_path: Path) -> None:
    text = "# what this thesis holds\n\nnodal staging\n! something far outside\n"
    assert kind_of(_written(tmp_path, "topics.md", text)) == "topics"


def test_the_control_marker_is_found_where_a_person_writes_it(tmp_path: Path) -> None:
    """Last, because it is the odd one out."""
    lines = ["# a preamble"] + [f"topic {n}" for n in range(80)] + ["! outside the field"]
    assert kind_of(_written(tmp_path, "topics.md", "\n".join(lines))) == "topics"


def test_a_list_with_no_control_marker_is_a_document(tmp_path: Path) -> None:
    """`coverage` refuses such a file, so nothing else may treat it as one."""
    assert kind_of(_written(tmp_path, "notes.md", "nodal staging\ndosimetry\n")) == "document"


def test_a_paper_is_a_document(tmp_path: Path) -> None:
    text = "<!-- page 1 -->\nHead-to-head comparison of two tracers\n\nAbstract\n"
    assert kind_of(_written(tmp_path, "paper.md", text)) == "document"


def test_anything_that_is_not_markdown_is_not_read(tmp_path: Path) -> None:
    assert kind_of(_written(tmp_path, "a.pdf", "whatever")) == "other"
    assert kind_of(_written(tmp_path, "a.json", "{}")) == "other"


def test_a_file_that_cannot_be_opened_is_not_a_document_with_no_quotations(
    tmp_path: Path,
) -> None:
    """An unreadable file is an unreadable file, not a pending item."""
    assert kind_of(tmp_path / "missing.md") == "other"


def test_nothing_outside_core_kinds_decides_this_again() -> None:
    """The rule this record exists for.

    `features/stages.py` and `features/overview.py` each held their own copy, and by the time
    anybody counted, the window offered **38** documents to quote from where `status` counted
    **29** - two coverage reports, a topics file and six extracted sections (ADR-090).

    A module is suspect when it holds the marks *and* a function that returns kind names. The
    marks alone are fine: a writer has to write them.
    """
    kinds = {"corpus", "bibliography", "review", "coverage", "topics", "extract", "document"}
    guilty: list[str] = []
    for path in sorted(SOURCE.rglob("*.py")):
        if path.name == "kinds.py" or path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            returned = {
                inner.value.value
                for inner in ast.walk(node)
                if isinstance(inner, ast.Return)
                and isinstance(inner.value, ast.Constant)
                and isinstance(inner.value.value, str)
            }
            if len(returned & kinds) >= 2:
                guilty.append(f"{path.relative_to(SOURCE)}::{node.name}")
    assert not guilty, (
        f"these decide what a file is, and core/kinds.py already does: {guilty}. "
        "Two copies of this drifted nine files apart once (ADR-090)."
    )
