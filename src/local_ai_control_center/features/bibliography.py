"""Writing down what a registry said, so it can be handed in (ADR-067).

Pure. Works in, Markdown out, and the one rule it keeps is the reason the whole feature
exists: **an empty field is a fact and a filled-in one is a claim.** A model asked for a
journal name supplied twelve out of twenty-four from memory, with an instruction in the same
prompt not to (ADR-047). Nothing here fills a gap. A field the registry did not hold is
printed as missing, by name.
"""

from __future__ import annotations

from local_ai_control_center.ports.registry import Work

_FIELDS = (("title", "title"), ("authors", "authors"), ("container", "journal"), ("year", "year"))


def missing_from(work: Work) -> tuple[str, ...]:
    """Which of the fields a citation needs the registry did not hold, in reading order."""
    return tuple(shown for attribute, shown in _FIELDS if not getattr(work, attribute))


def as_entry(work: Work) -> str:
    """One work on one line, in the order a reader expects, with the gaps named.

    Not a citation style. Which span is the title depends on the publisher, and formatting
    to APA or Vancouver is what a reference manager does from a DOI - this exists so a
    person can see what a work is and paste a correct identifier into that manager
    (ADR-064).
    """
    parts: list[str] = []
    if work.authors:
        named = "; ".join(work.authors[:3])
        parts.append(f"{named} et al." if len(work.authors) > 3 else named)
    if work.title:
        parts.append(f"*{work.title}*")
    if work.container:
        parts.append(work.container)
    if work.year:
        parts.append(str(work.year))
    line = ". ".join(parts) if parts else "**The registry holds nothing under this DOI.**"
    return f"{line}  <{work.doi}>"


def bibliography(
    resolved: list[Work], unknown: list[str], unresolvable: list[str], registry: str
) -> str:
    """The whole file: what was resolved, what the registry did not hold, what had no DOI.

    The three groups are kept apart on purpose. "The registry does not hold this" and "this
    work printed no DOI" are different facts about different problems, and a bibliography
    that merged them would hide which one a reader has to go and fix.
    """
    lines = [
        "# Bibliography",
        "",
        f"{len(resolved)} works resolved against {registry}. Every field below is what the "
        "registry holds; nothing here was generated, and a field it did not hold is named "
        "as missing rather than filled in.",
        "",
    ]
    if resolved:
        dated = {work.fetched_on for work in resolved if work.fetched_on}
        when = ", ".join(sorted(dated))
        lines += [f"*Received {when}.* A record can change after that date.", ""]
        lines += ["## Resolved", ""]
        for work in sorted(resolved, key=lambda w: (w.year or 0, w.title)):
            lines.append(f"- {as_entry(work)}")
            gaps = missing_from(work)
            if gaps:
                lines.append(f"  - *Not in the registry record: {', '.join(gaps)}.*")
        lines.append("")
    if unknown:
        lines += [
            "## The registry holds nothing for these",
            "",
            "A DOI that resolves to nothing is usually a DOI that was mangled in "
            "extraction, and occasionally one that was never registered.",
            "",
        ]
        lines += [f"- `{doi}`" for doi in sorted(unknown)]
        lines.append("")
    if unresolvable:
        lines += [
            "## No DOI to resolve",
            "",
            f"{len(unresolvable)} documents carry no DOI of their own, so nothing could be "
            "asked about them. This is the measured ceiling of this route, not a failure: "
            "most bibliographies do not print DOIs (ADR-064).",
            "",
        ]
        lines += [f"- {name}" for name in sorted(unresolvable)]
        lines.append("")
    return chr(10).join(lines)
