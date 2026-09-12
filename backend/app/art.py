"""A module's cover: which pattern, and which colour.

Six geometric patterns and eight colours, drawn in the page rather than
uploaded. No image is stored, no file is served, and a module with no choice
recorded still has a cover, because one is derived from its id.

The whole of it lives in one nullable column, `module.art`, holding a value
like `hexagons.teal`. One column rather than two because the pair is only ever
read and written together, and a half-chosen cover is not a state worth being
able to represent.

Nothing here touches the database or the request. It is a vocabulary and two
functions, so the form, the service, and the template all agree on what a valid
cover is without any of them defining it a second time.
"""

from __future__ import annotations

#: In the order they are offered. The first is the default for a new module.
#:
#: Four are drawn from the Najdi vocabulary, and three of those are one wall
#: read from top to bottom: the stepped merlons that crown it, the pierced
#: triangular openings set into it, and the arcade that carries it. The zigzag
#: frieze runs across all three. They are a geometric reading of that
#: vocabulary rather than a reproduction of any particular historical work.
PATTERNS: tuple[str, ...] = (
    "shurfat",
    "mushabak",
    "zigzag",
    "uqud",
    "diamonds",
    "circles",
)

#: What the picker calls each one. The keys are what is stored and what CSS is
#: written against, so they stay ASCII and stay still; only these change if a
#: name is ever reworded.
LABELS: dict[str, str] = {
    "shurfat": "Shurfat",
    "mushabak": "Mushabak",
    "zigzag": "Zigzag",
    "uqud": "Uqud",
    "diamonds": "Diamonds",
    "circles": "Circles",
}

#: One line each, because a name alone does not say what a tile looks like.
DESCRIPTIONS: dict[str, str] = {
    "shurfat": "Stepped merlons, as they crown a Najdi wall",
    "mushabak": "Pierced triangles, set in alternating rows",
    "zigzag": "A running zigzag frieze",
    "uqud": "An arcade of pointed arches",
    "diamonds": "Small interlocking rhombi",
    "circles": "Overlapping circles, offset by row",
}

#: Drawn from the same palette as the rest of the interface, and measured
#: against it: each is legible in both themes at the weight these are drawn.
COLOURS: tuple[str, ...] = (
    "indigo",
    "sky",
    "teal",
    "green",
    "amber",
    "rose",
    "violet",
    "slate",
)

SEPARATOR = "."


class InvalidArt(Exception):
    """A pattern or colour outside the vocabulary above."""


def parse(value: str | None, module_id: int) -> tuple[str, str]:
    """The pattern and colour to draw, always.

    A module with nothing recorded, or with something unrecognised recorded,
    falls back to a cover derived from its id. That is what lets the column be
    added without backfilling a single row, and what stops a module ever
    rendering an empty box.
    """
    if value:
        pattern, _, colour = value.partition(SEPARATOR)
        if pattern in PATTERNS and colour in COLOURS:
            return pattern, colour

    return derive(module_id)


def derive(module_id: int) -> tuple[str, str]:
    """A cover from the id alone.

    The two lists are different lengths, so walking the ids gives a different
    pairing each time rather than the same pattern always wearing the same
    colour.
    """
    number = module_id or 0
    return PATTERNS[number % len(PATTERNS)], COLOURS[number % len(COLOURS)]


def format(pattern: str, colour: str) -> str:
    """The stored value, refusing anything outside the vocabulary.

    Validated here rather than at the form, so a crafted request is refused on
    the same rule a select box is built from.
    """
    if pattern not in PATTERNS:
        raise InvalidArt(f"Unknown pattern: {pattern}")
    if colour not in COLOURS:
        raise InvalidArt(f"Unknown colour: {colour}")
    return f"{pattern}{SEPARATOR}{colour}"
