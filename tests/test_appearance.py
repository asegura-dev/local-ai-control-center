"""Where the window opens, as arithmetic that needs no display (ADR-100).

Left to Windows, the window opened wherever the last one had been offset to - 156 pixels
below a 1140-pixel work area on its second opening, with the status bar off the screen.
"""

from __future__ import annotations

from local_ai_control_center.features.appearance import FRAME, placement

WIDTH, HEIGHT = 1280, 820


def test_on_the_screen_it_was_found_on_it_opens_whole_at_the_top() -> None:
    """1920 by 1140 of work area at 125%: the default size fits, centred, at the top."""
    wide, tall, across, top = placement((0, 0, 1920, 1140), 1.25, WIDTH, HEIGHT)
    assert (wide, tall) == (WIDTH, HEIGHT)
    assert top == 0
    assert across == (1920 - round(WIDTH * 1.25)) // 2
    assert top + round(tall * 1.25) + FRAME <= 1140


def test_a_short_screen_gets_a_shorter_window_rather_than_one_off_its_edge() -> None:
    wide, tall, _, top = placement((0, 0, 1366, 728), 1.0, WIDTH, HEIGHT)
    assert tall == 728 - FRAME
    assert wide == WIDTH
    assert top + tall + FRAME <= 728


def test_a_taskbar_at_the_top_moves_the_window_below_it() -> None:
    _, _, _, top = placement((0, 40, 1920, 1080), 1.0, WIDTH, HEIGHT)
    assert top == 40


def test_a_higher_scaling_shrinks_what_is_asked_for_in_logical_pixels() -> None:
    wide, tall, _, _ = placement((0, 0, 1920, 1040), 1.5, WIDTH, HEIGHT)
    assert round(tall * 1.5) + FRAME <= 1040
    assert round(wide * 1.5) <= 1920


def test_a_narrow_screen_is_never_exceeded_across() -> None:
    wide, _, across, _ = placement((0, 0, 1024, 768), 1.0, WIDTH, HEIGHT)
    assert wide == 1024
    assert across == 0
