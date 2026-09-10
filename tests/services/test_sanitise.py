"""The sanitiser.

The only test in this phase whose failure would be silent in production: a hole
here produces no error, no crash, and no complaint, just content that executes
in every trainee's browser.
"""

from __future__ import annotations

import pytest

from app.sanitise import sanitise


# ------------------------------------------------------------ what is removed


@pytest.mark.parametrize(
    "dangerous",
    [
        "<script>alert(1)</script>",
        "<SCRIPT>alert(1)</SCRIPT>",
        "<img src=x onerror=alert(1)>",
        '<div onclick="alert(1)">click</div>',
        '<a href="javascript:alert(1)">go</a>',
        '<iframe src="https://example.com"></iframe>',
        "<object data='x'></object>",
        "<embed src='x'>",
        "<form action='/admin/accounts'><button>go</button></form>",
        '<p style="position:fixed;top:0">covered</p>',
    ],
)
def test_dangerous_markup_does_not_survive(dangerous):
    cleaned = sanitise(dangerous)
    lowered = cleaned.lower()

    assert "<script" not in lowered
    assert "onerror" not in lowered
    assert "onclick" not in lowered
    assert "javascript:" not in lowered
    assert "<iframe" not in lowered
    assert "<object" not in lowered
    assert "<embed" not in lowered
    assert "<form" not in lowered
    assert "style=" not in lowered


def test_a_script_beside_good_content_leaves_the_good_content():
    cleaned = sanitise("<p>Hello</p><script>alert(1)</script>")
    assert "<p>Hello</p>" in cleaned
    assert "script" not in cleaned.lower()


def test_a_dangerous_link_loses_its_target_not_its_text():
    cleaned = sanitise('<a href="javascript:alert(2)">click</a>')
    assert "javascript:" not in cleaned.lower()
    assert "click" in cleaned


# ------------------------------------------------------------- what survives


@pytest.mark.parametrize(
    "allowed",
    [
        "<h2>Heading</h2>",
        "<h3>Sub</h3>",
        "<p>Ordinary text</p>",
        "<strong>bold</strong>",
        "<em>italic</em>",
        "<u>underline</u>",
        "<ul><li>one</li><li>two</li></ul>",
        "<ol><li>first</li></ol>",
        "<blockquote>quoted</blockquote>",
        "<pre><code>code()</code></pre>",
    ],
)
def test_ordinary_formatting_is_preserved(allowed):
    tag = allowed.split(">")[0].lstrip("<")
    assert f"<{tag}" in sanitise(allowed)


def test_a_safe_link_keeps_its_href():
    cleaned = sanitise('<a href="https://example.com">example</a>')
    assert 'href="https://example.com"' in cleaned


def test_mailto_is_allowed():
    assert "mailto:" in sanitise('<a href="mailto:a@b.com">mail</a>')


def test_an_image_keeps_src_and_alt():
    cleaned = sanitise('<img src="/uploads/abc.png" alt="A diagram">')
    assert "/uploads/abc.png" in cleaned
    assert "A diagram" in cleaned


# ------------------------------------------------------------------ edge cases


def test_empty_and_none_are_empty():
    assert sanitise("") == ""
    assert sanitise(None) == ""


def test_a_long_body_is_not_truncated():
    body = "<p>" + ("word " * 5000) + "</p>"
    assert len(sanitise(body)) > 20_000
