"""Three ways to draw a mail's body, none of which lets anything run or load from the internet.

- `plain(text)`: the mail's text as written, escaped, with the earlier mail it quotes folded away;
- `tidied(html, images)`: the HTML kept to a small set of tags (paragraphs, breaks, emphasis, links,
  lists, quotes, headings, tables, pictures), with every attribute dropped but a link's address, a
  picture's source and description, and a table cell's span; styles dropped; the earlier mail a
  reply quotes (Gmail's, Outlook's and Apple Mail's ways of marking it) folded away;
- `original(html, images)`: the mail's own HTML with its styles, but without scripts, event
  handlers, `javascript:` addresses, frames, objects, forms or anything loaded from the internet
  (pictures, style sheets, `url(...)` in styles), inside a frame that runs nothing
  (`<iframe sandbox srcdoc=…>`) so its styles stay inside it.

A picture sent inside the mail (`src="cid:…"`) is pointed at its file through `images` (Content-ID
→ path); a remote picture is never fetched: it is left out. A link may point anywhere (it is only
followed when clicked). Built on the standard library's HTML parser, which never fails on bad HTML.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Optional

#: Tags kept by `tidied` (their attributes are dropped but for those in TIDY_ATTRIBUTES).
TIDY_TAGS = {
    "p", "br", "div", "b", "strong", "i", "em", "u", "s", "sub", "sup", "small", "a", "ul", "ol",
    "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "table", "thead", "tbody", "tfoot",
    "tr", "td", "th", "img", "pre", "code", "hr",
}  # fmt: skip
TIDY_ATTRIBUTES = {"a": {"href"}, "img": {"src", "alt"}, "td": {"colspan", "rowspan"},
                   "th": {"colspan", "rowspan"}}  # fmt: skip
#: Dropped with everything inside them, in both ways.
DROP_WITH_CONTENT = {"script", "noscript", "iframe", "frame", "frameset", "object", "embed",
                     "applet", "template", "svg", "math", "select", "textarea", "button", "title"}  # fmt: skip
#: Dropped, their contents kept (`original`); also never kept by `tidied`.
DROP_TAG = {"form", "input", "link", "meta", "base", "head", "html", "body"}
VOID = {"br", "img", "hr", "input", "link", "meta", "base", "col", "area", "source", "wbr"}
#: How mail programs mark the earlier mail a reply quotes.
QUOTE_CLASSES = ("gmail_quote", "moz-cite-prefix", "yahoo_quoted", "protonmail_quote")
QUOTE_IDS = ("appendonsend", "divrplyfwdmsg", "mail-editor-reference-message-container")
EARLIER = "Earlier mail"
_REMOTE_URL = re.compile(r"url\(\s*(['\"]?)\s*(?:https?:)?//[^)]*\)", re.IGNORECASE)
_IMPORT = re.compile(r"@import[^;]*;?", re.IGNORECASE)
_SAFE_LINK = re.compile(r"^\s*(https?:|mailto:|tel:|#)", re.IGNORECASE)
_PLAIN_QUOTE = re.compile(
    r"^(?:>|On .+wrote:\s*$|Em .+escreveu:\s*$|El .+escribió:\s*$|-{2,} ?Original Message ?-{2,}"
    r"|-{5,} Forwarded message)",
    re.IGNORECASE,
)


def _clean_style(text: str) -> str:
    """CSS with nothing loaded from the internet and nothing that runs."""
    text = _IMPORT.sub("", text)
    text = _REMOTE_URL.sub("none", text)
    return re.sub(r"expression\s*\(|javascript:|behavior\s*:", "", text, flags=re.IGNORECASE)


def _picture(value: str, images: dict[str, str]) -> Optional[str]:
    """Where a picture's source points: its file for a `cid:`, itself for a data image, else none."""
    value = value.strip()
    if value.lower().startswith("cid:"):
        return images.get(value[4:].strip("<> "))
    if re.match(r"data:image/(png|jpe?g|gif|webp);base64,", value, re.IGNORECASE):
        return value
    return None


class _Cleaner(HTMLParser):
    def __init__(self, mode: str, images: dict[str, str]) -> None:
        super().__init__(convert_charrefs=True)
        self.mode, self.images = mode, images
        self.out: list[str] = []
        self.dropping = 0  # inside a tag dropped with its content
        self.in_style = False
        self.stack: list[tuple[str, bool, bool]] = []  # (tag, written, opened a fold)
        self.folded = 0

    def _quote(self, tag: str, attrs: dict[str, str]) -> bool:
        if self.mode != "tidied" or self.folded:
            return False
        classes = attrs.get("class", "").lower()
        ident = attrs.get("id", "").lower()
        return (
            any(c in classes for c in QUOTE_CLASSES)
            or any(i in ident for i in QUOTE_IDS)
            or (tag == "blockquote" and attrs.get("type", "").lower() == "cite")
        )

    def handle_starttag(self, tag: str, given: list[tuple[str, Optional[str]]]) -> None:
        if self.dropping:
            if tag in DROP_WITH_CONTENT and tag not in VOID:
                self.dropping += 1
            return
        if tag in DROP_WITH_CONTENT:
            self.dropping = 1
            return
        attrs = {k.lower(): (v or "") for k, v in given}
        if tag == "style":
            if self.mode == "original":
                self.out.append("<style>")
                self.in_style = True
            else:
                self.dropping = 1  # tidied drops styles with what is in them
            return
        fold = self._quote(tag, attrs)
        if fold:
            self.out.append(f'<details class="quoted"><summary>{EARLIER}</summary>')
            self.folded += 1
        keep = (tag in TIDY_TAGS) if self.mode == "tidied" else (tag not in DROP_TAG)
        written = False
        if keep:
            text = self._open(tag, attrs)
            if text is not None:
                self.out.append(text)
                written = True
        if tag not in VOID:
            self.stack.append((tag, written, fold))

    def _open(self, tag: str, attrs: dict[str, str]) -> Optional[str]:
        kept: list[tuple[str, str]] = []
        for name, value in attrs.items():
            if name.startswith("on") or name in ("srcset", "formaction", "action", "background"):
                continue
            if self.mode == "tidied" and name not in TIDY_ATTRIBUTES.get(tag, set()):
                continue
            if name in ("href", "xlink:href"):
                if not _SAFE_LINK.match(value):
                    continue
            elif name == "src":
                pointed = _picture(value, self.images)
                if pointed is None:
                    return None if tag == "img" else ""  # a remote picture is left out
                value = pointed
            elif name == "style":
                value = _clean_style(value)
            kept.append((name, value))
        if tag == "a" and any(n == "href" for n, _ in kept):
            kept.append(("rel", "noopener noreferrer"))
        if tag == "img" and not any(n == "src" for n, _ in kept):
            return None
        joined = "".join(f' {n}="{html.escape(v, quote=True)}"' for n, v in kept)
        return f"<{tag}{joined}>"

    def handle_endtag(self, tag: str) -> None:
        if self.dropping:
            if tag in DROP_WITH_CONTENT or (tag == "style" and self.mode != "original"):
                self.dropping -= 1
            return
        if tag == "style" and self.in_style:
            self.out.append("</style>")
            self.in_style = False
            return
        if not any(t == tag for t, _, _ in self.stack):
            return
        while self.stack:
            open_tag, written, fold = self.stack.pop()
            if written:
                self.out.append(f"</{open_tag}>")
            if fold:
                self.out.append("</details>")
                self.folded -= 1
            if open_tag == tag:
                return

    def handle_data(self, data: str) -> None:
        if self.dropping:
            return
        if self.in_style:
            self.out.append(_clean_style(data).replace("</", "<\\/"))
        else:
            self.out.append(html.escape(data, quote=False))

    def result(self) -> str:
        self.close()
        while self.stack:
            open_tag, written, fold = self.stack.pop()
            if written:
                self.out.append(f"</{open_tag}>")
            if fold:
                self.out.append("</details>")
        return "".join(self.out)


def tidied(source: str, images: dict[str, str]) -> str:
    """The HTML kept to a small set of tags, without styles, its earlier mail folded away."""
    cleaner = _Cleaner("tidied", images)
    cleaner.feed(source)
    return cleaner.result().strip()


def original(source: str, images: dict[str, str], title: str = "The mail as it was sent") -> str:
    """The mail's own HTML with its styles, made safe, in a frame that runs nothing."""
    cleaner = _Cleaner("original", images)
    cleaner.feed(source)
    document = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        "<style>body{margin:0;font-family:system-ui,sans-serif;overflow-wrap:anywhere}"
        "img{max-width:100%;height:auto}</style></head><body>"
        f"{cleaner.result()}</body></html>"
    )
    return (
        f'<iframe class="mailframe" sandbox="" title="{html.escape(title, quote=True)}" '
        f'srcdoc="{html.escape(document, quote=True)}"></iframe>'
    )


def plain(text: str) -> str:
    """The text as written, escaped; from the first line that quotes earlier mail, folded away."""
    lines = text.replace("\r\n", "\n").split("\n")
    cut = next((i for i, line in enumerate(lines) if _PLAIN_QUOTE.match(line.strip())), None)
    own = "\n".join(lines if cut is None else lines[:cut]).strip("\n")
    body = f'<div class="text">{html.escape(own, quote=False)}</div>'
    if cut is not None:
        rest = html.escape("\n".join(lines[cut:]).strip("\n"), quote=False)
        body += f'<details class="quoted"><summary>{EARLIER}</summary><div class="text">{rest}</div></details>'
    return body
