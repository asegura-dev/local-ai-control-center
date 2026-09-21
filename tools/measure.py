"""Take the measurements this project argues from, in one run.

**Every figure here is taken now.** Nothing is stored, because a number in a file is a number
that will be true for a while and then quietly stop being - which is the failure this project
has recorded twelve times, six of them flattering (`docs/04-measurements.md`). A figure you
can re-take in four seconds never needs to be trusted.

It measures nothing new. It runs the counts that have been done by hand at the point of
needing them, so that arguing from measurement is the cheap option rather than the diligent
one:

    .\\run.ps1 run python tools/measure.py                  the project
    .\\run.ps1 run python tools/measure.py ~/lacc-workspace  the project and the material

What each section is for is written above it, because a number whose question is not stated
is decoration.
"""

from __future__ import annotations

import ast
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "local_ai_control_center"

PAGE_MARKER = re.compile(r"<!--\s*page\s+\d+\s*-->", re.IGNORECASE)
HEADING = re.compile(r"(?m)^#{1,6} .*$")
NUMBERED_SECTION = re.compile(r"(?m)^\s{0,3}\d{1,2}(?:\.\d{1,2})?\.?\s+[A-Z][A-Za-z \-]{3,60}\s*$")
CHARS_PER_TOKEN = 3
"""The estimate the rest of the project budgets with, repeated rather than imported so this
tool keeps running if the package will not import."""


def _rule(title: str, asks: str) -> None:
    print()
    print(title.upper())
    print(f"  {asks}")
    print()


def _tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


# --- the project ---------------------------------------------------------------------------


def _layers() -> None:
    _rule("layers", "Where does the code live, and is any one file becoming the program?")
    rows: list[tuple[str, int, int]] = []
    for layer in ("core", "ports", "adapters", "features", "system"):
        files = [p for p in (SOURCE / layer).rglob("*.py") if p.name != "__init__.py"]
        lines = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in files)
        rows.append((layer, len(files), lines))
    root = [p for p in SOURCE.glob("*.py") if p.name != "__init__.py"]
    rows.append(
        (
            "root (views + cycle)",
            len(root),
            sum(len(p.read_text(encoding="utf-8").splitlines()) for p in root),
        )
    )
    whole = sum(lines for _, _, lines in rows) or 1
    print(f"  {'layer':24} {'files':>6} {'lines':>8} {'share':>7}")
    for name, count, lines in rows:
        print(f"  {name:24} {count:6} {lines:8,} {100 * lines / whole:6.1f}%")
    print(f"  {'':24} {sum(c for _, c, _ in rows):6} {whole:8,}")

    biggest = max(root, key=lambda p: len(p.read_text(encoding="utf-8").splitlines()))
    share = 100 * len(biggest.read_text(encoding="utf-8").splitlines()) / whole
    print()
    print(f"  largest single file: {biggest.name} at {share:.0f}% of all code")


def _view_logic() -> None:
    _rule(
        "logic in the views",
        "Has anything that decides something drifted into a view? (ADR-066)",
    )
    presentation = {
        "Console",
        "_console",
        "_show",
        "Progress",
        "Panel",
        "Table",
        "Text",
        "print",
        "echo",
        "confirm",
        "_approve",
        "_confirm",
        "CTk",
        "CTkFrame",
        "CTkLabel",
        "CTkButton",
        "CTkFont",
        "CTkScrollableFrame",
        "Treeview",
        "configure",
        "pack",
        "grid",
        "insert",
        "destroy",
        "winfo_children",
        "mainloop",
        "bind",
        "after",
    }
    for name in ("cli.py", "window.py"):
        path = SOURCE / name
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for inner in node.body:
                    if isinstance(inner, ast.FunctionDef) and inner.name != "__init__":
                        functions.setdefault(f"{node.name}.{inner.name}", inner)

        def names(fn: ast.AST) -> set[str]:
            found: set[str] = set()
            for x in ast.walk(fn):
                if isinstance(x, ast.Name):
                    found.add(x.id)
                elif isinstance(x, ast.Attribute):
                    found.add(x.attr)
            return found

        reaches = {k: bool(names(v) & presentation) for k, v in functions.items()}
        plain = {k.split(".")[-1]: k for k in functions}
        calls = {k: {plain[c] for c in names(v) & set(plain)} for k, v in functions.items()}
        changed = True
        while changed:
            changed = False
            for k in functions:
                if not reaches[k] and any(reaches[c] for c in calls[k]):
                    reaches[k] = changed = True
        astray = sorted(k for k, v in reaches.items() if not v)
        print(f"  {name:12} {len(functions):3} functions, {len(astray):2} never touch presentation")
        for found in astray:
            print(f"                 {found}")


def _records() -> None:
    _rule("records", "Is every decision written down, and does the count match the index?")
    adr = sorted((ROOT / "docs" / "adr").glob("ADR-*.md"))
    indexed = (ROOT / "docs" / "adr" / "README.md").read_text(encoding="utf-8")
    missing = [p.name for p in adr if p.name not in indexed]
    print(f"  records on disk    {len(adr)}")
    print(f"  not in the index   {len(missing)}" + (f"  -> {missing}" if missing else ""))
    chapters = sorted((ROOT / "docs").glob("*.md"))
    guides = sorted((ROOT / "docs" / "guides").glob("*.md"))
    book = sorted((ROOT / "docs" / "book").glob("*.md"))
    print(f"  chapters {len(chapters)}, guides {len(guides)}, book {len(book)}")


def _suite() -> None:
    _rule("suite", "How many checks, and do they pass right now?")
    try:
        done = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "pytest", "-q", "--no-header", "-x", "--co", "-q"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
        # Two `-q` make pytest print "file: n" per file and no total, so the total is the
        # sum of them. Read from the output rather than assumed, like everything else here.
        per_file = [
            int(line.rsplit(":", 1)[1])
            for line in done.stdout.splitlines()
            if line.strip().endswith(tuple("0123456789"))
            and ":" in line
            and line.rsplit(":", 1)[1].strip().isdigit()
        ]
        files = len(list((ROOT / "tests").glob("test_*.py")))
        if per_file:
            print(f"  {sum(per_file):,} checks across {len(per_file)} of {files} test files")
        else:
            print(f"  pytest printed no counts; {files} test files are on disk")
    except (OSError, subprocess.SubprocessError) as error:
        print(f"  could not run pytest: {error}")


# --- the material --------------------------------------------------------------------------


def _documents(workspace: pathlib.Path) -> None:
    _rule(
        "documents",
        "How large is the material, and what does its structure cost? (ADR-073)",
    )
    papers = sorted(p for p in workspace.glob("*.md") if not p.name.startswith("."))
    if not papers:
        print(f"  nothing in {workspace}")
        return
    print(f"  {'document':44} {'tokens':>9} {'pages':>6} {'marks':>7} {'heads':>6} {'numbered':>9}")
    total = marked = 0
    without_structure = 0
    for path in papers[:40]:
        text = path.read_text(encoding="utf-8", errors="replace")
        tokens = _tokens(text)
        marks = PAGE_MARKER.findall(text)
        mark_tokens = sum(_tokens(m) for m in marks)
        heads = HEADING.findall(text)
        numbered = NUMBERED_SECTION.findall(text)
        total += tokens
        marked += mark_tokens
        without_structure += not heads and len(numbered) < 3
        print(
            f"  {path.name[:44]:44} {tokens:9,} {len(marks):6} "
            f"{mark_tokens:7,} {len(heads):6} {len(numbered):9}"
        )
    print()
    print(f"  {len(papers)} documents, {total:,} tokens in the first {min(len(papers), 40)}")
    print(f"  page markers cost {100 * marked / (total or 1):.1f}% of the text they make locatable")
    print(f"  {without_structure} have neither headings nor numbered sections")


def _corpora(workspace: pathlib.Path) -> None:
    _rule("corpora", "What is collected, and how much of it is citable?")
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from local_ai_control_center.core.corpus import parse_corpus
    except ImportError as error:
        print(f"  the package would not import: {error}")
        return
    for path in sorted(workspace.glob("*.md")):
        opening = path.read_text(encoding="utf-8", errors="replace")[:200]
        if not opening.startswith(("# Collected quotations", "# Claims collected by")):
            continue
        claims = parse_corpus(path.read_text(encoding="utf-8", errors="replace"))
        placed = sum(1 for c in claims if c.page)
        refused = sum(1 for c in claims if "NOT IN THE DOCUMENT" in c.recorded_verdict)
        with_claim = sum(1 for c in claims if c.claim)
        sources = len({c.document for c in claims})
        print(f"  {path.name}")
        print(
            f"      {len(claims):,} quotations   {placed:,} with a page   "
            f"{refused} refused   {with_claim:,} carry a paraphrase   {sources} documents"
        )


def main() -> int:
    """Print every measurement, and the workspace ones when a folder is given."""
    print("=" * 78)
    print("LACC - measurements taken now, stored nowhere")
    print("=" * 78)
    _layers()
    _view_logic()
    _records()
    _suite()
    if len(sys.argv) > 1:
        workspace = pathlib.Path(sys.argv[1]).expanduser()
        if workspace.is_dir():
            _documents(workspace)
            _corpora(workspace)
        else:
            print(f"\n  {workspace} is not a folder")
    else:
        print("\n  Pass a workspace to measure the material too.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
