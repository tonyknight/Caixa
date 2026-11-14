"""Speech-to-text says how it is getting on: in the progress bar, the job's log and the terminal."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from chattr.transcription import Transcript
from fixtures import family

from caixa import serve
from caixa.box import Box
from caixa.collectors.base import Progress
from caixa.collectors.chattr import TimedTranscriber
from caixa.collectors.options import validate
from caixa.collectors.registry import discover
from caixa.service import TERMINAL_MARK, _Terminal


class Slow:
    """A stand-in engine: each recording "takes" two seconds on the clock it is given."""

    def __init__(self, clock: list[float], fail_on: str = "") -> None:
        self.clock, self.fail_on = clock, fail_on

    def transcribe(self, audio: Path) -> Transcript:
        self.clock[0] += 2.0
        if self.fail_on and self.fail_on in audio.name:
            raise RuntimeError("whisper.cpp failed")
        return Transcript(f"words from {audio.name}", "en", "stand-in")


def test_each_recording_reports_its_time_against_its_length(
    capsys: pytest.CaptureFixture[str],
) -> None:
    clock, steps = [100.0], []
    timed = TimedTranscriber(
        Slow(clock), steps.append, clock=lambda: clock[0], length=lambda a: 30.0
    )
    timed.expect(2)
    assert timed.transcribe(Path("1.amr")).text == "words from 1.amr"
    timed.transcribe(Path("2.amr"))
    assert [(s.stage, s.current, s.total) for s in steps] == [
        ("transcribing", 0, 2),
        ("transcribing", 0, 2),
        ("transcribing", 1, 2),
        ("transcribing", 1, 2),
        ("transcribing", 2, 2),
    ]
    assert steps[1].message == "Listening to 1.amr"
    assert (
        steps[2].message == "1.amr: 2.0 s for 30 s of audio (15.0x real time); average 2.0 s each"
    )
    printed = capsys.readouterr().out.splitlines()
    assert printed[0].startswith("Speech-to-text 1/2: 1.amr: 2.0 s") and len(printed) == 2


def test_a_recording_that_fails_is_still_counted_and_said(
    capsys: pytest.CaptureFixture[str],
) -> None:
    clock, steps = [0.0], []
    timed = TimedTranscriber(
        Slow(clock, fail_on="2"), steps.append, clock=lambda: clock[0], length=lambda a: None
    )
    timed.expect(2)
    timed.transcribe(Path("1.amr"))
    with pytest.raises(RuntimeError):
        timed.transcribe(Path("2.amr"))
    assert steps[-1].current == 2 and "failed: whisper.cpp failed" in steps[-1].message
    assert "failed" in capsys.readouterr().out


def test_an_import_with_speech_to_text_shows_a_transcribing_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [0.0]
    monkeypatch.setattr("caixa.collectors.chattr.make_transcriber", lambda *a, **k: Slow(clock))
    archive = tmp_path / "Voicemail.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for day in (1, 2, 3):
            z.writestr(f"vm/(2019-01-0{day}) 10 00 00 - {family.ANA.name}.amr", f"audio {day}")
    box = Box.create(tmp_path / "Box", "Test box")
    collector = discover().get("voicemail")
    events: list[Progress] = []
    options = validate(collector.info.options_schema, {"transcribe": True, "model": "x"})
    result = collector.run(box, archive, options, events.append)
    assert result.inserted == 3
    heard = [e for e in events if e.stage == "transcribing"]
    assert [e.current for e in heard if e.message.startswith("Listening")] == [0, 1, 2]
    assert heard[-1].current == heard[-1].total == 3 and "average" in heard[-1].message
    page = "".join(p.read_text("utf-8") for p in (box.root / "People").rglob("(*.html"))
    assert "words from (2019-01-01) 10 00 00" in page


def test_the_terminal_hears_each_stage_and_each_recording_but_not_every_step() -> None:
    out = io.StringIO()
    tell = _Terminal(7, interval=3600, out=out)
    for n in range(50):
        tell(Progress("importing", n, 50, f"thread {n}"))
    tell(Progress("transcribing", 0, 2, "Listening to 1.amr"))
    tell(Progress("transcribing", 1, 2, "1.amr: 2.0 s; average 2.0 s each"))
    tell(Progress("transcribing", 1, 2, "1.amr: 2.0 s; average 2.0 s each"))
    lines = out.getvalue().splitlines()
    assert lines == [
        f"{TERMINAL_MARK}job 7: importing 0/50 - thread 0",
        f"{TERMINAL_MARK}job 7: transcribing 0/2 - Listening to 1.amr",
        f"{TERMINAL_MARK}job 7: transcribing 1/2 - 1.amr: 2.0 s; average 2.0 s each",
    ]


def test_the_mark_is_the_one_caixa_serve_listens_for() -> None:
    assert serve.TERMINAL_MARK == TERMINAL_MARK


class Batch(Slow):
    """An engine that takes every recording in one run; the first waits for the model to load."""

    def transcribe_many(self, files):
        self.clock[0] += 6.0  # loading the model, once
        for audio in files:
            self.clock[0] += 1.0
            failed = self.fail_on and self.fail_on in audio.name
            yield audio, (RuntimeError("bad audio") if failed else Transcript("words", "en", "m"))


def test_a_run_of_many_recordings_times_each_as_it_comes_out(
    capsys: pytest.CaptureFixture[str],
) -> None:
    clock, steps = [0.0], []
    timed = TimedTranscriber(
        Batch(clock, fail_on="2"), steps.append, clock=lambda: clock[0], length=lambda a: 20.0
    )
    timed.expect(3)
    results = list(timed.transcribe_many([Path("1.amr"), Path("2.amr"), Path("3.amr")]))
    assert [audio.name for audio, _ in results] == ["1.amr", "2.amr", "3.amr"]
    assert steps[1].message == "Loading the speech model (once)"
    assert [s.current for s in steps[2:]] == [1, 2, 3]
    assert "1.amr: 7.0 s for 20 s of audio" in steps[2].message
    assert "includes loading the model" in steps[2].message
    assert "2.amr: 1.0 s" in steps[3].message and "failed: bad audio" in steps[3].message
    assert steps[4].message.endswith("average 3.0 s each")
    assert len(capsys.readouterr().out.splitlines()) == 3


def test_an_engine_that_cannot_take_many_is_not_offered_as_one() -> None:
    timed = TimedTranscriber(Slow([0.0]), lambda step: None)
    assert not hasattr(timed, "transcribe_many")
