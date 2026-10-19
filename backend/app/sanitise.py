"""HTML sanitising for page content (allowlist based).

Content is sanitised before it is saved, so the database never holds unsafe HTML.
"""

from __future__ import annotations

import nh3

# Anything not listed (script, iframe, style, on* handlers, ...) is removed.
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

# No javascript: or data: links.
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
