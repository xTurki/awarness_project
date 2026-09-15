"""A module's cover: an uploaded picture, or a plain colour.

Nothing is drawn any more. A module wears a picture its administrator
uploaded, and until one is uploaded it wears a single colour, so a list of
modules stays legible without anybody having to choose anything.

An administrator picks the colour when they make the module. One that was
never picked is derived from the module id instead, so a module always has a
colour and nobody is forced to choose one to get past the form.

So the column `module.art` holds `teal`, or `upload.9f2c....png`, or nothing at
all. A row holding something older, from when covers were drawn patterns, means
the same as nothing: neither a colour nor an upload, so the colour comes from
the id.

Nothing here touches the database or the request. It is one list and three
functions, so the service and the template agree on what a valid cover is
without either of them defining it a second time.
"""

from __future__ import annotations

import re

#: Drawn from the same palette as the rest of the interface, and measured
#: against it: each is legible in both themes behind the text that sits on it.
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

#: What an uploaded cover is written as: `upload.9f2c....png`. The prefix is
#: what tells a stored value apart from anything the column held before.
UPLOAD = "upload"

#: A stored name as `content_service` generates it: `uuid4().hex` and an
#: extension. Matched rather than trusted, so nothing that reached this column
#: can name a path, a parent directory, or a file outside the uploads volume.
_STORED_NAME = re.compile(r"^[0-9a-f]{32}\.[a-z0-9]{1,8}$")


class InvalidArt(Exception):
    """A cover value outside the vocabulary above."""


def colour_for(module_id: int) -> str:
    """The colour a module wears when nobody picked one, from its id alone.

    Total: every id has one, including `None` and zero, so no module can reach
    a template without a colour and no template has to decide what to do about
    its absence.
    """
    return COLOURS[(module_id or 0) % len(COLOURS)]


def parse_colour(value: str | None, module_id: int) -> str:
    """The colour to paint, always.

    A stored colour wins. Anything else falls through to the id: no value at
    all, an uploaded picture (whose own colour nobody needed to pick), or a
    leftover from when covers were drawn patterns. All three mean the same
    thing here, which is why none of them is a special case.
    """
    if value in COLOURS:
        return value
    return colour_for(module_id)


def format_colour(colour: str) -> str:
    """The stored value for a picked colour, refusing anything else.

    Validated here rather than at the form, so a crafted request is refused on
    the same rule the picker is built from.
    """
    if colour not in COLOURS:
        raise InvalidArt(f"Unknown colour: {colour}")
    return colour


def uploaded(value: str | None) -> str | None:
    """The stored file name when the cover is an uploaded picture, else `None`.

    `None` covers three different cases on purpose, because they all render the
    same way: no cover was ever set, the cover was removed, or the column still
    holds a drawn pattern from before drawn patterns were taken out.
    """
    if not value:
        return None

    kind, _, name = value.partition(SEPARATOR)
    if kind != UPLOAD:
        return None

    return name if _STORED_NAME.match(name) else None


def format_upload(stored_name: str) -> str:
    """The stored value for an uploaded cover, refusing any other shape.

    Validated here rather than at the caller, so one definition of a valid
    cover serves the route, the service and the template.
    """
    if not _STORED_NAME.match(stored_name or ""):
        raise InvalidArt(f"Not a stored image name: {stored_name}")
    return f"{UPLOAD}{SEPARATOR}{stored_name}"
