"""Three ways to draw a mail's body, and none of them lets a script, a handler or a remote file in."""

from __future__ import annotations

import html
import re

import pytest

from caixa.mail.render import original, plain, tidied

UNSAFE = (
    "<html><head><script>document.title='x'</script>"
    '<link rel="stylesheet" href="https://cdn.example.com/a.css">'
    "<style>body{background:url(https://tracker.example.com/bg.png)} p{color:#336}</style></head>"
    '<body onload="track()"><p style="font-weight:bold" onclick="x()">Lovely, thank you.</p>'
    '<img src="https://tracker.example.com/b.gif" width="1" height="1">'
    '<a href="javascript:alert(1)">bad</a> <a href="https://example.org/book">the book</a>'
    '<iframe src="https://example.org/frame"></iframe><form action="https://example.org/f">'
    '<input name="q"></form><object data="x.swf"></object>'
    '<p>Beatriz<br><img src="cid:logo.png.beatriz-3@noisy.example" alt="logo"></p>'
    "<div style=\"background-image: url('https://tracker.example.com/c.png')\">x</div>"
    "</body></html>"
)
IMAGES = {"logo.png.beatriz-3@noisy.example": "files/(2023-02-02) logo.png"}


def _safe(page: str) -> None:
    """Nothing that runs, and nothing loaded from the internet (a link's address is only followed
    when clicked, so links may point anywhere)."""
    lowered = html.unescape(html.unescape(page)).lower()  # the original is escaped into its frame
    assert "<script" not in lowered
    assert not re.search(r"\son[a-z]+\s*=", lowered)
    assert "javascript:" not in lowered
    assert not re.search(r"src\s*=\s*[\"']?\s*https?://", lowered)
    assert not re.search(r"url\(\s*['\"]?\s*https?://", lowered)
    assert "<iframe src" not in lowered and "<object" not in lowered and "<form" not in lowered
    assert "<link" not in lowered


@pytest.mark.parametrize("draw", [tidied, original])
def test_html_is_drawn_without_scripts_handlers_or_remote_files(draw) -> None:  # type: ignore[no-untyped-def]
    page = draw(UNSAFE, IMAGES)
    _safe(page)
    assert "Lovely, thank you." in page
    assert "files/(2023-02-02) logo.png" in page  # the picture sent with the mail
    assert "tracker.example.com" not in page


def test_links_keep_their_address() -> None:
    for page in (tidied(UNSAFE, IMAGES), original(UNSAFE, IMAGES)):
        assert 'href="https://example.org/book"' in html.unescape(page)


def test_tidied_keeps_the_structure_and_drops_the_styles() -> None:
    page = tidied(UNSAFE, IMAGES)
    assert "<p>Lovely, thank you.</p>" in page
    assert "style" not in page and "color" not in page


def test_tidied_folds_the_earlier_replies() -> None:
    html = (
        "<p>Yes, Thursday works.</p>"
        '<div class="gmail_quote">On Mon, Ana wrote:<blockquote>Lunch on Thursday?</blockquote></div>'
    )
    page = tidied(html, {})
    assert page.index("Yes, Thursday works.") < page.index("<details")
    assert "Lunch on Thursday?" in page.split("<details", 1)[1]


def test_original_keeps_its_own_styles_in_a_frame_that_runs_nothing() -> None:
    page = original(UNSAFE, IMAGES)
    assert page.startswith("<iframe") and 'sandbox=""' in page and "srcdoc=" in page
    assert "font-weight:bold" in page and "p{color:#336}" in page


def test_plain_text_is_escaped_and_its_quotes_folded() -> None:
    page = plain("Thanks!\n<b>not bold</b>\n\n> On Monday Ana wrote:\n> Lunch?\n")
    assert "&lt;b&gt;not bold&lt;/b&gt;" in page
    assert page.index("Thanks!") < page.index("<details")
    assert "Lunch?" in page.split("<details", 1)[1]


def test_the_originals_frame_is_sized_to_its_mail() -> None:
    short = original("<p>Hi.</p>", {})
    long = original("<p>" + "word " * 2000 + "</p>", {})

    def rem(page: str) -> float:
        found = re.search(r'style="height:\s*([\d.]+)rem"', page)
        assert found, page[:120]
        return float(found.group(1))

    assert 4 <= rem(short) < 10 < rem(long) <= 60


def test_the_safe_html_lives_in_chattr_and_caixa_uses_it() -> None:
    import chattr.mail_html as chattr_html

    from caixa.mail import render

    assert render.original is chattr_html.original
    assert render.tidied is chattr_html.tidied and render.plain is chattr_html.plain
