"""The cover vocabulary: six patterns, eight colours, one nullable column.

The important property is the fallback. `art` is nullable and nothing was
backfilled when the column was added to a live database, so every module that
existed before this feature must still render a cover. If `parse` ever returns
None, those modules get an empty box.
"""

from __future__ import annotations

import pytest

from app import art


# ------------------------------------------------------------- the vocabulary


def test_four_of_the_six_are_najdi():
    """Hexagons, pentagons, triangles and squares were replaced. Diamonds and
    circles stayed, because they were not asked to go."""
    assert art.PATTERNS == (
        "shurfat", "mushabak", "zigzag", "uqud", "diamonds", "circles",
    )

    for retired in ("hexagons", "pentagons", "triangles", "squares", "darraj"):
        assert retired not in art.PATTERNS


def test_every_pattern_has_a_name_and_a_line_about_it():
    """A key alone does not tell somebody what a tile looks like, and a picker
    built from a key with no label shows raw storage to the person using it."""
    assert set(art.LABELS) == set(art.PATTERNS)
    assert set(art.DESCRIPTIONS) == set(art.PATTERNS)
    assert all(art.LABELS[name].strip() for name in art.PATTERNS)
    assert all(art.DESCRIPTIONS[name].strip() for name in art.PATTERNS)


def test_there_are_eight_colours():
    assert len(art.COLOURS) == 8
    assert len(set(art.COLOURS)) == 8


def test_that_is_forty_eight_covers():
    assert len(art.PATTERNS) * len(art.COLOURS) == 48


# ------------------------------------------------------------------ storing


def test_a_choice_round_trips():
    stored = art.format("shurfat", "teal")

    assert stored == "shurfat.teal"
    assert art.parse(stored, module_id=1) == ("shurfat", "teal")


@pytest.mark.parametrize("pattern", art.PATTERNS)
@pytest.mark.parametrize("colour", art.COLOURS)
def test_every_combination_survives_the_round_trip(pattern, colour):
    assert art.parse(art.format(pattern, colour), module_id=99) == (pattern, colour)


def test_an_unknown_pattern_is_refused():
    with pytest.raises(art.InvalidArt):
        art.format("octagons", "teal")


def test_a_retired_pattern_is_refused_like_any_other_unknown(): 
    """Nothing stored one, because the only module on the platform had chosen
    nothing, but a value left over from the old vocabulary must not be written
    back as if it were still valid."""
    for retired in ("hexagons", "pentagons", "triangles", "squares", "darraj"):
        with pytest.raises(art.InvalidArt):
            art.format(retired, "teal")


def test_a_retired_pattern_already_stored_falls_back_gracefully():
    """The same path as any unrecognised value: a cover from the id, never an
    empty box."""
    pattern, colour = art.parse("hexagons.teal", module_id=2)

    assert pattern in art.PATTERNS
    assert colour in art.COLOURS


def test_an_unknown_colour_is_refused():
    with pytest.raises(art.InvalidArt):
        art.format("shurfat", "puce")


# ----------------------------------------------- the fallback that matters


def test_a_module_with_nothing_chosen_still_gets_a_cover():
    """Every module that existed before the column did. Nothing was backfilled,
    so this is what stops them rendering an empty box."""
    pattern, colour = art.parse(None, module_id=1)

    assert pattern in art.PATTERNS
    assert colour in art.COLOURS


def test_a_meaningless_stored_value_falls_back_rather_than_breaking():
    for rubbish in ("", "nonsense", "hexagons", "hexagons.puce", "octagons.teal", "..."):
        pattern, colour = art.parse(rubbish, module_id=3)
        assert pattern in art.PATTERNS
        assert colour in art.COLOURS


def test_the_fallback_is_stable_for_a_given_module():
    assert art.parse(None, module_id=7) == art.parse(None, module_id=7)


def test_neighbouring_modules_fall_back_to_different_covers():
    covers = {art.parse(None, module_id=n) for n in range(1, 9)}

    # Six patterns and eight colours are coprime in neither direction, but the
    # differing lengths are what stop a pattern always wearing one colour.
    assert len(covers) == 8


def test_a_choice_always_beats_the_fallback():
    derived = art.derive(4)
    other = ("uqud", "rose") if derived != ("uqud", "rose") else ("circles", "sky")

    assert art.parse(art.format(*other), module_id=4) == other
