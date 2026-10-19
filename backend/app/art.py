"""Module cover helpers: an uploaded image or a colour.

`module.art` holds a colour name (e.g. `teal`), an upload (`upload.<name>.png`),
or nothing. When no colour is set, one is derived from the module id.
"""

from __future__ import annotations

import re

# Each colour has a matching `.module-art-<name>` class in app.css.
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

UPLOAD = "upload"

# Stored file name: uuid4 hex + extension. Validated so it can't be a path.
_STORED_NAME = re.compile(r"^[0-9a-f]{32}\.[a-z0-9]{1,8}$")


class InvalidArt(Exception):
    """Raised for an invalid cover value."""


def colour_for(module_id: int) -> str:
    """Default colour for a module, based on its id (works for None too)."""
    return COLOURS[(module_id or 0) % len(COLOURS)]


def parse_colour(value: str | None, module_id: int) -> str:
    """Return the stored colour, or the default colour for the module id."""
    if value in COLOURS:
        return value
    return colour_for(module_id)


def format_colour(colour: str) -> str:
    """Validate a colour name and return the value to store."""
    if colour not in COLOURS:
        raise InvalidArt(f"Unknown colour: {colour}")
    return colour


def uploaded(value: str | None) -> str | None:
    """Return the uploaded file name if the cover is an upload, else None."""
    if not value:
        return None

    kind, _, name = value.partition(SEPARATOR)
    if kind != UPLOAD:
        return None

    return name if _STORED_NAME.match(name) else None


def format_upload(stored_name: str) -> str:
    """Validate an uploaded file name and return the value to store."""
    if not _STORED_NAME.match(stored_name or ""):
        raise InvalidArt(f"Not a stored image name: {stored_name}")
    return f"{UPLOAD}{SEPARATOR}{stored_name}"
