# ADR-087 - The DOI a person established

## Status

Accepted. Most of this record is a rule that was measured and **refused**, and the decision
is what was left when it failed.

## Context

`lacc resolve` asks the registry about the DOI a document already carries - read from the
PDF's own metadata, never from a model. Measured over a real bibliography of 23 papers:

| | |
|---|---|
| PDFs carrying a DOI in their metadata | **11 of 23** |
| the Markdown made from those 11 carrying it | **0 of 11** |
| documents printing a DOI on their own front pages | **9 of the remaining 12** |

Two facts, and the second is the interesting one. **Conversion loses the DOI entirely** -
eleven of eleven - so the corpus is built from files that cannot be resolved, and this route
only works against the originals. And **nine documents print their DOI on the page** where
neither the metadata nor LACC was looking.

Nine of twelve is most of what is missing. So: read the DOI a document prints, and resolve it.

## The rule that was measured and refused

The obvious objection is that a document also prints the DOIs of everything it **cites**. One
of the twelve is a GLOBOCAN country fact sheet whose only two DOIs belong to papers it cites.
Taking the first DOI on the page would have put two wrong works into a bibliography.

The proposed separator: **ask the registry what the candidate is, and keep it only if the
title that comes back is the title the document prints.** A document's own title is on its
front page; a cited work's is not.

It is not, and the measurement says so plainly. Over the whole front matter:

| share of the registry's title found | document | verdict |
|---|---|---|
| **100%** | the fact sheet, `10.3322/caac.21660` | **cited, not its own** |
| **100%** | the fact sheet, `10.1002/ijc.33588` | **cited, not its own** |
| 100% | five documents | own |

A reference list prints the full title of what it cites, so a cited work scores as highly as
an owned one. Narrowing the window to the title block alone - 400 characters - did not rescue
it:

| window | best cited DOI | worst own DOI |
|---|---|---|
| 400 chars | **60%** | **0%** |
| 800 chars | 60% | 29% |
| 1500 chars | 60% | 42% |

**At every window a cited DOI outranks an owned one.** There is no threshold, and picking one
anyway would be this project's MinHash again: a feature justified by a premise that nobody had
checked, where checking it took minutes and killed it.

## Decision

**A DOI that cannot be derived is stated by a person, and recorded beside the file.**

    lacc identify <document>              lists the DOIs printed near its front, and asks
                                          the registry what each one is. Chooses nothing.
    lacc identify <document> --doi <doi>  asks the registry, shows the work it names, and
                                          on confirmation writes <document>.doi.json

`resolve` then reads that file for any document whose own metadata is silent, exactly as it
reads the metadata for the others.

**Beside the file, never inside it.** The corpus points at these documents as they are and
hundreds of quotations are checked against them; writing a line into one would change a file
that eight hundred string comparisons depend on. It joins `report.findings.json`,
`bibliografia.registry.json` and `part.md.from.json` - facts *about* a file, kept next to it.

**The listing proposes and the person disposes**, which is what the measurement leaves. Nine
documents print a DOI; a human looking at the registry's title beside the document's own
opening separates own from cited in a second, and no rule tried here separates them at all.
That is the human-in-the-loop principle doing actual work rather than decorating a dialog.

**It records why.** The file carries the DOI, the title the registry gave for it, and the date
- so a bibliography rebuilt later rests on what was received and confirmed, not on somebody's
recollection of having checked.

## Consequences

- Eight of the nine printed DOIs are the document's own and one document's two are not. That
  takes the bibliography of the user's **own sources** from 11 of 23 to 19 of 23.
- The four that remain are two arXiv preprints, a guideline and a fact sheet, none of which
  prints a DOI of its own. That is a ceiling of the material, not of the tool.
- `resolve` gains no new network behaviour: the same request, for a DOI that arrived from a
  different place.

## Trade-off

**A person can write down the wrong DOI.** The defence is that they are shown what the
registry says that DOI *is* before it is written, which is the same defence every confirmation
in this program has - and it is stronger than the alternative, because the alternative was
measured and does not work at all.

**It is manual, and a bibliography of two hundred would make that painful.** It is not for
two hundred: it is for the handful a person actually read, whose originals are on their own
disk. The cited references keep arriving in bulk through `resolve --cited`.

**And a `.doi.json` can drift from its document**, as any fact kept beside a file can. It is
named after the file and moves only if somebody moves one without the other - the same
exposure `.from.json` and `.findings.json` already carry, accepted for the same reason.
