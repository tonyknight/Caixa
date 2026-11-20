"""`caixa mail sample`: a few conversations drawn three ways, to choose how mail bodies look."""

from __future__ import annotations

import html
import re
import shutil
from pathlib import Path

import pytest
from fixtures.builders.noisy_mbox import MAILBOX_NAME, NoisyMail

from caixa import cli
from caixa.mail.index import MailIndex
from caixa.mail.sample import STYLES, sample


def _safe(page: str) -> None:
    lowered = html.unescape(html.unescape(page)).lower()
    assert "<script" not in lowered
    assert not re.search(r"<[^>]+\son[a-z]+\s*=", lowered)
    assert "javascript:" not in lowered
    assert not re.search(r"src\s*=\s*[\"']?\s*https?://", lowered)
    assert not re.search(r"url\(\s*['\"]?\s*https?://", lowered)


def test_conversations_are_drawn_three_ways(tmp_path: Path, noisy_mail: NoisyMail) -> None:
    index = MailIndex(tmp_path / "index.sqlite")
    (read,) = index.read(noisy_mail.gmail, account="Gmail")
    out = tmp_path / "samples"
    result = sample(index, read.source_id, out, conversations=4)
    assert STYLES == ("plain", "tidied", "original")
    for style in STYLES:
        pages = sorted((out / style).glob("*.html"))
        assert len(pages) == 4, style
        for page in pages:
            _safe(page.read_text(encoding="utf-8"))
    front = (out / "index.html").read_text(encoding="utf-8")
    assert front.count('href="plain/') == front.count('href="original/') == 4
    assert result.conversations == 4
    book = next((out / "tidied").glob("*Book club in March*.html")).read_text(encoding="utf-8")
    assert book.count('class="card"') == 3  # three mails, three cards
    assert "Beatriz Lima" in book and "beatriz.lima@example.net" in book
    assert "maria.costa@example.com" in book  # the recipients
    assert "All headers" in book and "X-Gmail-Labels" in book
    logos = sorted((out / "files").rglob("logo.png"))
    assert logos and "../files/" in book


def test_the_command_line_samples(
    tmp_path: Path, noisy_mail: NoisyMail, capsys: pytest.CaptureFixture[str]
) -> None:
    box = tmp_path / "Box"
    assert cli.main(["box", "create", str(box), "--name", "Our box"]) == 0
    mbox = Path(shutil.copy(noisy_mail.gmail, tmp_path / MAILBOX_NAME))
    capsys.readouterr()
    out = tmp_path / "look"
    code = cli.main(["mail", "sample", str(mbox), "--account", "Gmail", "--out", str(out),
                     "--conversations", "2", "--box", str(box)])  # fmt: skip
    printed = capsys.readouterr().out
    assert code == 0 and str(out / "index.html") in printed
    assert len(list((out / "original").glob("*.html"))) == 2


def test_pictures_inside_the_originals_frame_are_part_of_the_page(
    tmp_path: Path, noisy_mail: NoisyMail
) -> None:
    """A frame that runs nothing cannot load a file from disk, so its pictures travel inside it."""
    index = MailIndex(tmp_path / "index.sqlite")
    (read,) = index.read(noisy_mail.gmail, account="Gmail")
    sample(index, read.source_id, tmp_path / "out", conversations=4)
    book = next((tmp_path / "out" / "original").glob("*Book club in March*.html"))
    inner = html.unescape(book.read_text(encoding="utf-8"))
    assert "data:image/png;base64," in inner and "cid:" not in inner
