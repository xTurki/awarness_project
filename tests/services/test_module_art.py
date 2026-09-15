"""The cover vocabulary: eight colours, and a file name when one was uploaded.

Nothing is drawn any more. What is left is a colour derived from the module id
and, when an administrator uploaded one, the name of a file.

Two properties carry this module. The colour is **total**: every id has one, so
no module can reach a template without a cover. And `uploaded` is **strict**:
the column is the only thing standing between a stored value and a path on
disk, so anything that is not a name this platform generated resolves to no
file at all.
"""

from __future__ import annotations

import pytest

from app import art


# ------------------------------------------------------------- the vocabulary


def test_nothing_is_drawn_any_more():
    """The six Najdi patterns went, then the five cybersecurity covers went
    with them. A module wears a picture or a colour, and nothing is drawn."""
    for gone in ("PATTERNS", "TILED", "LABELS", "DESCRIPTIONS", "derive"):
        assert not hasattr(art, gone), f"art.{gone} should have been removed"


def test_there_are_eight_colours():
    assert len(art.COLOURS) == 8
    assert len(set(art.COLOURS)) == 8


# ---------------------------------------------------------------- the colour


def test_every_module_has_a_colour():
    """Total, so no template ever has to decide what an absent cover means."""
    for module_id in range(0, 50):
        assert art.colour_for(module_id) in art.COLOURS


def test_a_missing_id_still_gives_a_colour():
    assert art.colour_for(None) in art.COLOURS
    assert art.colour_for(0) in art.COLOURS


def test_the_colour_is_stable_for_a_given_module():
    """It is derived, not stored, so it must not wander between two reads of
    the same row."""
    assert art.colour_for(7) == art.colour_for(7)


def test_neighbouring_modules_differ():
    """A list of modules that were all one colour would be no better than a
    list of modules with no colour at all."""
    assert len({art.colour_for(n) for n in range(1, 9)}) == 8


# ------------------------------------------------------------ a picked colour


def test_a_picked_colour_is_the_one_worn():
    """It beats the id, which is the whole point of picking."""
    for name in art.COLOURS:
        assert art.parse_colour(name, module_id=3) == name


def test_nothing_picked_falls_back_to_the_id():
    assert art.parse_colour(None, module_id=3) == art.colour_for(3)
    assert art.parse_colour("", module_id=3) == art.colour_for(3)


def test_a_colour_outside_the_palette_falls_back_rather_than_breaking():
    """A crafted value reaches this column the same way a real one does."""
    for bad in ("puce", "#ff0000", "red", "TEAL", "teal.green"):
        assert art.parse_colour(bad, module_id=3) == art.colour_for(3)


def test_an_uploaded_cover_falls_back_for_its_colour():
    """The colour under a picture is nobody's choice, because the picture
    covers it. Removing the picture leaves the id's colour behind."""
    stored = art.format_upload("0123456789abcdef0123456789abcdef.png")

    assert art.parse_colour(stored, module_id=3) == art.colour_for(3)


def test_a_colour_round_trips():
    assert art.parse_colour(art.format_colour("teal"), module_id=9) == "teal"


def test_formatting_refuses_a_colour_outside_the_palette():
    for bad in ("puce", "", "#ff0000"):
        with pytest.raises(art.InvalidArt):
            art.format_colour(bad)


def test_a_stored_colour_is_not_an_upload():
    """Both live in one column, so each has to say no about the other."""
    for name in art.COLOURS:
        assert art.uploaded(name) is None


# ---------------------------------------------------------- uploaded covers


def test_no_value_means_no_picture():
    assert art.uploaded(None) is None
    assert art.uploaded("") is None


def test_a_value_left_over_from_the_drawn_covers_means_no_picture():
    """Rows still hold `uqud.green` and `shield.teal` from when covers were
    drawn. Neither is an upload, so both mean the module wears its colour, and
    that is why removing the patterns needed no migration."""
    for stale in ("uqud.green", "shield.teal", "firewall.amber", "diamonds.sky"):
        assert art.uploaded(stale) is None


def test_an_upload_value_gives_back_the_file_name():
    name = "0123456789abcdef0123456789abcdef.png"
    assert art.uploaded(f"upload.{name}") == name


def test_a_name_the_platform_did_not_generate_is_refused():
    """The column is the only thing between this value and a path on disk."""
    for bad in (
        "upload.../../etc/passwd",
        "upload./etc/passwd",
        "upload.not-a-uuid.png",
        "upload.0123456789abcdef0123456789abcdef",          # no extension
        "upload.0123456789ABCDEF0123456789ABCDEF.png",      # not lower case
        "upload.",
        "upload",
    ):
        assert art.uploaded(bad) is None, bad


# --------------------------------------------------------------- formatting


def test_a_stored_name_round_trips():
    name = "0123456789abcdef0123456789abcdef.jpg"

    assert art.format_upload(name) == f"upload.{name}"
    assert art.uploaded(art.format_upload(name)) == name


def test_formatting_refuses_the_shapes_reading_refuses():
    for bad in ("../x.png", "x.png", "", "0123456789abcdef0123456789abcdef"):
        with pytest.raises(art.InvalidArt):
            art.format_upload(bad)


def test_the_stored_value_fits_the_column():
    """`module.art` is VARCHAR(64), and the longest value this can produce is
    the word, a separator, 32 hex characters and an extension."""
    longest = art.format_upload("0123456789abcdef0123456789abcdef.jpeg")
    assert len(longest) <= 64
