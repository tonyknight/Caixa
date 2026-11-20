"""Reading a mailbox of gigabytes: memory stays bounded and more workers are faster.

Slow (it writes a 2 GB synthetic mbox), so it is left out of the default run:
`python -m pytest -q -m slow tests/test_mail_scale.py -s`. Each read runs in a fresh process, so
the peak memory it reports is the read's own (the main process, and the largest worker).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fixtures.builders.noisy_mbox import write_large_mbox

SIZE = 2 * 1024**3
LIMIT_MB = 500
#: About the size of a real mail with its attachments (a Takeout of 2 GB holds tens of thousands).
AVERAGE = 40_000

READ = """
import json, resource, sys, time
from caixa.mail.index import MailIndex
index = MailIndex(sys.argv[2])
started = time.monotonic()
(result,) = index.read(sys.argv[1], account="Gmail", workers=int(sys.argv[3]))
seconds = time.monotonic() - started
scale = 1 if sys.platform == "darwin" else 1024  # ru_maxrss is bytes on macOS, KiB elsewhere
mine = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale
children = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * scale
print(json.dumps({"mails": result.mails, "seconds": seconds, "self": mine, "children": children}))
"""


def _read(mbox: Path, index: Path, workers: int) -> dict[str, float]:
    done = subprocess.run(
        [sys.executable, "-c", READ, str(mbox), str(index), str(workers)],
        capture_output=True,
        text=True,
        check=True,
    )
    return dict(json.loads(done.stdout.strip().splitlines()[-1]))


@pytest.mark.slow
def test_a_two_gigabyte_mbox_in_bounded_memory_and_faster_with_workers(tmp_path: Path) -> None:
    mbox = tmp_path / "large.mbox"
    count = write_large_mbox(mbox, SIZE, average=AVERAGE)
    most = min(os.cpu_count() or 1, 12)
    one = _read(mbox, tmp_path / "one.sqlite", 1)
    many = _read(mbox, tmp_path / "many.sqlite", most)
    for label, run in (("1 worker", one), (f"{most} workers", many)):
        print(
            f"\n{label}: {run['mails']:,.0f} mails ({SIZE / 1024**3:.0f} GB) in "
            f"{run['seconds']:.1f} s; peak memory {run['self'] / 2**20:.0f} MB "
            f"(largest worker {run['children'] / 2**20:.0f} MB)"
        )
    assert one["mails"] == many["mails"] == count
    for run in (one, many):
        assert run["self"] < LIMIT_MB * 2**20
        assert run["children"] < LIMIT_MB * 2**20
    if most > 1:
        assert many["seconds"] < one["seconds"]
