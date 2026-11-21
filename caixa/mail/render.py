"""Three ways to draw a mail's body safely: Chattr's `chattr.mail_html`, which draws the box's mail
pages (see there). Caixa's sample (`caixa mail sample`) uses it through this name."""

from __future__ import annotations

from chattr.mail_html import EARLIER, original, plain, tidied

__all__ = ["EARLIER", "original", "plain", "tidied"]
