"""One allowlist and one function.

Kept out of `content_service` deliberately, so the thing every trainee's browser
depends on is one small file with its own test module rather than a helper
buried among page CRUD.

**This runs before the body is written, never at render time.** Content written
once is read by every trainee on the module. Sanitising on display would mean
every future template that forgets a filter is a hole; sanitising before storage
means the column cannot hold anything unsafe in the first place (FR-016).

An allowlist rather than a blocklist, because blocklists are a losing game: the
interesting cases are always the encoding nobody thought of.
"""

from __future__ import annotations

import nh3

# What the editor can produce and a trainee needs to read. Everything absent
# from this set is removed, including style, every on* handler, script, iframe,
# object, embed, and form.
ALLOWED_TAGS: set[str] = {
    "p", "br",
    "h2", "h3", "h4",
    "strong", "em", "u",
    "ul", "ol", "li",
    "a",
    "blockquote",
    "code", "pre",
    "img",
}

ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title", "width"},
}

# A link may only go somewhere a link should go. javascript: is absent, and so
# is data:.
ALLOWED_URL_SCHEMES: set[str] = {"http", "https", "mailto"}


def sanitise(html: str | None) -> str:
    """Return HTML safe to store and render as-is."""
    if not html:
        return ""
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer",
    )
