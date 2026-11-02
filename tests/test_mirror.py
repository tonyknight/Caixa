"""The Chattr mirror: `git subtree split` pushed as a fast-forward, never forced."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "tools" / "mirror" / "mirror-chattr.sh"
#: Chattr's published main branch (its own repository) when the history was imported into Caixa.
CHATTR_PUBLISHED_MAIN = "0152912a57dfa4642f1b255507c5260779ebb4e1"

_probe = subprocess.run(["git", "subtree"], capture_output=True, text=True)
pytestmark = pytest.mark.skipif(
    "usage: git subtree" not in _probe.stdout + _probe.stderr,
    reason="git subtree is not available",
)


def git(cwd: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=Test Person", "-c", "user.email=test@example.com", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def commit(repo: Path, files: dict[str, str], message: str) -> None:
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def mirror(repo: Path, remote: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), "--remote", str(remote), *extra],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def caixa(tmp_path: Path) -> Path:
    repo = tmp_path / "caixa"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    commit(repo, {"README.md": "caixa", "tools/chattr/README.md": "chattr 1"}, "start")
    commit(repo, {"caixa/x.py": "x = 1"}, "caixa only")
    commit(repo, {"tools/chattr/src/a.py": "a = 1"}, "chattr: add a")
    return repo


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    path = tmp_path / "chattr.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(path)], check=True)
    return path


def _log(repo: Path, ref: str) -> list[str]:
    return git(repo, "log", "--format=%s", ref).splitlines()


def test_the_first_run_pushes_the_subtrees_history_only(caixa: Path, remote: Path) -> None:
    result = mirror(caixa, remote)
    assert result.returncode == 0, result.stderr
    assert _log(remote, "main") == ["chattr: add a", "start"]  # "caixa only" did not touch it
    tree = git(remote, "ls-tree", "-r", "--name-only", "main").splitlines()
    assert tree == ["README.md", "src/a.py"]  # the prefix is gone: Chattr's own layout
    assert git(remote, "show", "main:README.md") == "chattr 1"


def test_later_commits_fast_forward(caixa: Path, remote: Path) -> None:
    mirror(caixa, remote)
    before = git(remote, "rev-parse", "main")
    commit(caixa, {"tools/chattr/src/b.py": "b = 1"}, "chattr: add b")
    result = mirror(caixa, remote)
    assert result.returncode == 0, result.stderr
    assert git(remote, "merge-base", "--is-ancestor", before, "main", check=False) == ""
    subprocess.run(["git", "merge-base", "--is-ancestor", before, "main"], cwd=remote, check=True)
    assert _log(remote, "main")[0] == "chattr: add b" and len(_log(remote, "main")) == 3


def test_commits_elsewhere_change_nothing(caixa: Path, remote: Path) -> None:
    mirror(caixa, remote)
    before = git(remote, "rev-parse", "main")
    commit(caixa, {"caixa/y.py": "y = 1", "docs/notes.md": "n"}, "caixa again")
    result = mirror(caixa, remote)
    assert result.returncode == 0 and "up to date" in result.stdout.lower()
    assert git(remote, "rev-parse", "main") == before


def test_authors_dates_and_messages_survive_the_split(caixa: Path, remote: Path) -> None:
    mirror(caixa, remote)
    original = git(caixa, "log", "--format=%an|%ae|%at|%s", "-1", "--", "tools/chattr")
    assert git(remote, "log", "--format=%an|%ae|%at|%s", "-1", "main") == original


def test_a_dry_run_pushes_nothing(caixa: Path, remote: Path) -> None:
    result = mirror(caixa, remote, "--dry-run")
    assert result.returncode == 0 and "would push" in result.stdout.lower()
    assert git(remote, "branch", "--list") == ""


def test_a_remote_that_has_moved_on_is_refused_and_left_alone(
    caixa: Path, remote: Path, tmp_path: Path
) -> None:
    mirror(caixa, remote)
    other = tmp_path / "someone-else"
    subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
    commit(other, {"surprise.txt": "pushed straight to Chattr"}, "direct commit")
    git(other, "push", "-q", "origin", "main")
    before = git(remote, "rev-parse", "main")
    commit(caixa, {"tools/chattr/src/c.py": "c = 1"}, "chattr: add c")
    result = mirror(caixa, remote)
    assert result.returncode != 0
    assert "not a fast-forward" in (result.stdout + result.stderr).lower()
    assert git(remote, "rev-parse", "main") == before and "direct commit" in _log(remote, "main")


def test_the_script_never_forces(caixa: Path, remote: Path) -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "--force" not in text and "+refs" not in text and "force-with-lease" not in text
    assert "push" in text


def test_credentials_in_the_remote_url_are_never_printed(caixa: Path) -> None:
    url = "https://x-access-token:s3cr3t-value@example.invalid/tonyknight/Chattr.git"
    result = subprocess.run(
        ["bash", str(SCRIPT), "--remote", url, "--dry-run"],
        cwd=caixa,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    assert result.returncode != 0  # nothing to reach
    assert "s3cr3t-value" not in result.stdout + result.stderr
    assert "***@" in result.stdout + result.stderr


def test_a_missing_remote_argument_is_explained(caixa: Path) -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT)], cwd=caixa, capture_output=True, text=True, check=False
    )
    assert result.returncode == 2 and "--remote" in result.stderr


def test_the_real_history_descends_from_chattrs_published_main() -> None:
    have = subprocess.run(
        ["git", "cat-file", "-e", CHATTR_PUBLISHED_MAIN], cwd=REPO, capture_output=True
    )
    if have.returncode != 0:
        pytest.skip("a shallow clone: Chattr's imported history isn't here")
    split = git(REPO, "subtree", "split", "--prefix=tools/chattr")
    assert (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", CHATTR_PUBLISHED_MAIN, split], cwd=REPO
        ).returncode
        == 0
    ), "pushing the split to Chattr's repository would not be a fast-forward"


# --- The workflow, its documentation and the banner ------------------------------------------

WORKFLOW = REPO / ".github" / "workflows" / "mirror-chattr.yml"


def test_the_workflow_runs_the_script_on_pushes_to_main_with_full_history() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "push:" in text and "branches: [main]" in text
    assert "workflow_dispatch" in text  # and by hand
    assert "fetch-depth: 0" in text  # a subtree split needs the whole history
    assert "tools/mirror/mirror-chattr.sh" in text
    assert "concurrency:" in text  # one mirror run at a time
    assert "--force" not in text and "force-with-lease" not in text


def test_the_workflow_uses_a_secret_and_fails_clearly_without_one() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets.CHATTR_MIRROR_TOKEN" in text
    assert "CHATTR_MIRROR_TOKEN is not set" in text  # a plain message, not a push error
    assert "contents: read" in text  # the workflow's own token can only read Caixa
    assert "::add-mask::" in text  # the token never appears in a log


def test_the_workflow_never_writes_the_token_anywhere_it_could_leak() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "set -x" not in text and 'echo "$CHATTR_MIRROR_TOKEN"' not in text
    assert "persist-credentials: false" in text


def test_the_token_is_documented_for_the_maintainer() -> None:
    for readme in (REPO / "README.md", REPO / "tools" / "mirror" / "README.md"):
        text = readme.read_text(encoding="utf-8")
        assert "CHATTR_MIRROR_TOKEN" in text, readme
    guide = (REPO / "tools" / "mirror" / "README.md").read_text(encoding="utf-8")
    for needed in (
        "fine-grained",
        "Contents",
        "Read and write",
        "repository secret",
        "fast-forward",
    ):
        assert needed in guide, needed


def test_chattrs_readme_says_it_is_developed_in_caixa() -> None:
    first = (REPO / "tools" / "chattr" / "README.md").read_text(encoding="utf-8").splitlines()[:6]
    banner = "\n".join(first)
    assert "Developed in" in banner and "Caixa" in banner and "tools/chattr" in banner
