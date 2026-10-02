"""What a thesis protocol cites, and where (ADR-124).

Built from the shapes the thesis's own protocol uses: a master list with a key in bold and the
reference on the next line, numbers in brackets as lists and ranges, a state-of-the-art table
whose rows each cite one work, and tracers in brackets that are not citations.
"""

from __future__ import annotations

from local_ai_control_center.core.protocol import (
    MasterEntry,
    citing,
    citing_sentences,
    master_entries,
    numbers_in,
)

_MASTER = """# Referencias del protocolo: lista maestra

## Verificadas contra la fuente

- **rokuss** | compacto [19] | extenso [31] | verificada contra la fuente | con DOI
  Rokuss M, Kovacs B, et al. From FDG to PSMA. *arXiv*. 2024. doi:10.48550/arXiv.2409.09478.

- **andrearczyk** | extenso [33] | verificada contra la fuente | sin DOI: la sede no lo emite
  Andrearczyk V, Oreiller V, et al. Automatic segmentation of head and neck tumors. *PMLR*. 2020.

- **guan** | sin citar | verificada contra la fuente | con DOI
  Guan H, Liu M. Domain adaptation. *IEEE TBME*. 2022. doi:10.1109/TBME.2021.3117407.
"""


def test_the_master_list_gives_each_key_its_numbers_and_its_reference() -> None:
    entries = {entry.key: entry for entry in master_entries(_MASTER)}
    assert set(entries) == {"rokuss", "andrearczyk", "guan"}
    rokuss = entries["rokuss"]
    assert (rokuss.compact, rokuss.extended) == (19, 31)
    assert rokuss.doi == "10.48550/arXiv.2409.09478", "the stop after the DOI is not part of it"
    assert rokuss.reference.startswith("Rokuss M, Kovacs B")
    assert (entries["andrearczyk"].compact, entries["andrearczyk"].extended) == (None, 33)
    assert entries["andrearczyk"].doi == ""
    assert (entries["guan"].compact, entries["guan"].extended) == (None, None)


def test_a_citation_names_its_numbers_with_ranges_spelled_out() -> None:
    assert numbers_in("19") == (19,)
    assert numbers_in("2-4") == (2, 3, 4)
    assert numbers_in("8, 9") == (8, 9)
    assert numbers_in("15, 28, 29") == (15, 28, 29)
    assert numbers_in("44–46") == (44, 45, 46)


_CHAPTER = """# Antecedentes

El ensayo ALFA estableció la ventaja del método B sobre el A [3]. La variabilidad entre
lectores motiva soluciones asistidas [8, 11].

En visión por computadora destacan dos antecedentes: Pérez et al. 2020 [28] entrenaron una red.
El marcador [18F]FDG tiene captación inespecífica en el músculo [2-4].

| Referencia | Descripción |
|---|---|
| Gómez et al. 2024 [19] (Equipo Faro) | Propuesta ganadora del reto Beta. |
"""


def test_each_sentence_is_found_with_the_numbers_it_cites() -> None:
    found = citing_sentences(_CHAPTER, "compacto_03.md")
    numbers = [sentence.numbers for sentence in found]
    assert numbers == [(3,), (8, 11), (28,), (2, 3, 4), (19,)]
    assert all(sentence.source == "compacto_03.md" for sentence in found)


def test_et_al_and_a_year_do_not_end_a_sentence() -> None:
    found = citing_sentences(_CHAPTER, "c.md")
    earlier = next(sentence for sentence in found if 28 in sentence.numbers)
    assert earlier.text.startswith(
        "En visión por computadora destacan dos antecedentes: Pérez et al. 2020"
    )


def test_a_tracer_in_brackets_is_not_a_citation() -> None:
    found = citing_sentences(_CHAPTER, "c.md")
    tracer = next(sentence for sentence in found if "[18F]" in sentence.text)
    assert tracer.numbers == (2, 3, 4), "[18F] names a tracer, not a work"


def test_a_table_row_is_one_unit_and_its_line_is_its_own() -> None:
    found = citing_sentences(_CHAPTER, "c.md")
    row = next(sentence for sentence in found if 19 in sentence.numbers)
    assert row.text.startswith("Gómez et al. 2024 [19] (Equipo Faro) - Propuesta ganadora")
    assert (
        row.line
        == _CHAPTER.splitlines().index(
            "| Gómez et al. 2024 [19] (Equipo Faro) | Propuesta ganadora del reto Beta. |"
        )
        + 1
    )


def test_each_item_of_a_list_is_its_own_sentence() -> None:
    """The objectives, a list with no blank lines, were one "sentence" citing ten works."""
    chapter = (
        "# Objetivos particulares\n\n"
        "- Construir un flujo de datos reproducible [18, 32].\n"
        "- Entrenar un modelo base por partición [25].\n"
        "1. **Datos.** Convertir los archivos desde su formato original [29, 30].\n"
    )
    found = citing_sentences(chapter, "c.md")
    assert [sentence.numbers for sentence in found] == [(18, 32), (25,), (29, 30)]
    assert found[0].text == "Construir un flujo de datos reproducible [18, 32]."
    assert [sentence.line for sentence in found] == [3, 4, 5]


def test_the_marks_are_taken_out_of_what_a_judge_is_asked() -> None:
    found = citing_sentences(_CHAPTER, "c.md")
    assert found[1].without_marks == "La variabilidad entre lectores motiva soluciones asistidas."


def test_a_work_is_cited_by_its_number_in_each_version() -> None:
    rokuss = MasterEntry(key="rokuss", compact=19, extended=31)
    found = citing_sentences(_CHAPTER, "c.md")
    assert [sentence.numbers for sentence in citing(rokuss, found, "compact")] == [(19,)]
    assert citing(rokuss, found, "extended") == ()
    only_long = MasterEntry(key="andrearczyk", extended=33)
    assert citing(only_long, found, "compact") == ()
