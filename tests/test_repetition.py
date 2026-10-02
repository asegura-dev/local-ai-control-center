"""What a text says twice, found without a model (ADR-125).

Built from the shapes of the thesis protocol the rule was measured on: tracers' names whose
numbers are not figures, a graphics card's model, a section number, a percentage, a year,
citation marks, a display formula, and a summary table repeating a paragraph.
"""

from __future__ import annotations

from local_ai_control_center.core.repetition import (
    Stated,
    content_words,
    repetitions,
    same_fact,
    specific_figures,
    stated_in,
)


def test_a_tracers_name_carries_no_figure() -> None:
    """33 of the first rule's 64 pairs shared nothing but these."""
    assert specific_figures("en [68Ga]PSMA-11 PET/CT y [18F]PSMA-1007") == frozenset()


def test_the_figures_that_measure_something_are_kept() -> None:
    found = specific_figures("Dice de 0.517 en 549 pacientes y 2,616 ganglios, con 28% menos")
    assert found == {"0.517", "549", "2,616", "28"}


def test_a_year_a_pointer_and_a_name_are_not_figures() -> None:
    text = "En 2024, la sección 3.4 y la tabla 12 piden una RTX 5080 de 16 GB"
    assert specific_figures(text) == {"16"}


def test_a_round_number_is_a_setting_unless_it_is_a_percentage() -> None:
    assert specific_figures("1000 épocas de 250 iteraciones, lesiones de 10 mm") == frozenset()
    assert specific_figures("un 30% de los casos") == {"30"}


def test_a_decimal_after_a_name_in_capitals_is_kept() -> None:
    """`RTX 5080` names a card; `AUC 0.95` measures something."""
    assert specific_figures("AUC 0.95 en la RTX 5080") == {"0.95"}


def test_function_words_and_short_words_carry_nothing() -> None:
    assert content_words("La red para los ganglios, con the CT-only data") == {
        "ganglios",
        "data",
    }


_BACKGROUND = (
    "# Antecedentes\n"
    "\n"
    "En validación cruzada, el modelo de base alcanzó un Dice de 0.517 y el modelo final "
    "0.600 [31].\n"
    "\n"
    "| Referencia | Resultado |\n"
    "|---|---|\n"
    "| Gómez et al. 2024 [31] | Dice: 0.517 (modelo de base), 0.600 (modelo final). |\n"
    "| Pérez et al. 2020 [12] | Clasificador desde CT sola en [68Ga]PSMA-11, 549 pacientes. |\n"
    "\n"
    "$$\\mathcal{L} = 0.517 + 0.600$$\n"
)


def test_a_table_row_repeating_its_paragraph_is_one_group() -> None:
    groups = repetitions(stated_in(_BACKGROUND, "03.md"))
    assert len(groups) == 1
    assert [one.place for one in groups[0].sentences] == ["03.md:3", "03.md:7"]
    assert groups[0].figures == ("0.517", "0.600")


def test_a_display_formula_is_never_compared() -> None:
    lines = {one.line for one in stated_in(_BACKGROUND, "03.md")}
    assert 10 not in lines, "two formulas share symbols, not facts"


def test_a_shared_tracer_is_not_a_shared_fact() -> None:
    text = (
        "Un clasificador entrenado con CT anticipa el resultado en [68Ga]PSMA-11 de los ganglios.\n"
        "\n"
        "Otro estudio en [68Ga]PSMA-11 mostró que combinar marcadores ayuda.\n"
    )
    assert repetitions(stated_in(text, "a.md")) == ()


def test_two_sentences_of_one_paragraph_are_never_a_pair() -> None:
    text = "El Dice fue 0.517 y luego 0.600. Dicho otra vez, el Dice fue 0.517 y luego 0.600.\n"
    assert repetitions(stated_in(text, "a.md")) == ()


def _stated(line: int, words: frozenset[str], figures: frozenset[str] = frozenset()) -> Stated:
    return Stated(source="a.md", line=line, text="", figures=figures, words=words)


_EIGHT = frozenset(f"palabra{letter}" for letter in "abcdefgh")


def test_half_the_words_is_a_shared_fact_only_between_long_sentences() -> None:
    other = frozenset(sorted(_EIGHT)[:6]) | {"distinta", "otra"}
    assert same_fact(_stated(1, _EIGHT), _stated(9, other)), "6 of 10 words"
    four = frozenset(sorted(_EIGHT)[:4])
    assert not same_fact(_stated(1, four), _stated(9, four)), "four words shared by accident"


def test_one_figure_needs_a_fifth_of_the_words_beside_it() -> None:
    patients = frozenset({"378"})
    close = frozenset(sorted(_EIGHT)[:4]) | {f"otra{letter}" for letter in "abcd"}
    far = frozenset(sorted(_EIGHT)[:1]) | {f"otra{letter}" for letter in "abcdefg"}
    assert same_fact(_stated(1, _EIGHT, patients), _stated(9, close, patients)), "4 of 12"
    assert not same_fact(_stated(1, _EIGHT, patients), _stated(9, far, patients)), "1 of 15"


def test_pairs_that_share_a_sentence_join_one_group_largest_first() -> None:
    """An introduction repeating two rows of a table is one place to look."""
    text = (
        "El ensayo alcanzó 92% frente a 65%, con un VPP de 0.84 a 0.92.\n"
        "\n"
        "| Hofman et al. 2020 [3] | Exactitud de 92% contra 65%. |\n"
        "| Fendler et al. 2019 [4] | VPP entre 0.84 y 0.92. |\n"
        "\n"
        "Rokuss reporta un Dice de 0.517 y 0.600 en PSMA.\n"
        "\n"
        "Con nnU-Net estándar, 0.517; con el modelo final, 0.600.\n"
    )
    groups = repetitions(stated_in(text, "02.md"))
    assert [len(group.sentences) for group in groups] == [3, 2]
    assert groups[0].figures == ("0.84", "0.92", "65", "92")
