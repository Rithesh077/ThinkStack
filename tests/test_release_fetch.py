"""Fetching tags when some of them roll.

The beta and nightly channels publish to a MOVING tag -- `beta` and `nightly`
are republished at a new commit on every build, which is what makes
`releases/download/beta/...` a permanent URL for the newest beta.

Git refuses to move a tag it already has. So the second time anyone fetches,
once those tags have been republished:

    ! [rejected] beta    -> beta  (would clobber existing tag)
    ! [rejected] nightly -> nightly  (would clobber existing tag)

and `git fetch --tags` exits non-zero. Every release script treated that exit
code as "the network is down". `scripts/ship.sh` refuses to continue on it:

    ✗ could not reach origin - refusing to ship from stale refs.
        Check the network, then re-run.

which is a guard reporting a cause that is not the cause -- the network is
fine, and re-running never helps, because the local tag is still there. Stable
sat at v2.1.9 from 8 August while this was the message anyone trying to ship
would have seen.

These tests build a real remote and move a real tag.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True
    )


@pytest.fixture()
def remote_and_clone(tmp_path: Path) -> tuple[Path, Path]:
    """A bare remote carrying a rolling `beta` tag, and a clone of it."""
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    clone = tmp_path / "clone"

    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    git(work, "config", "user.email", "t@example.com")
    git(work, "config", "user.name", "t")
    (work / "f").write_text("1")
    git(work, "add", "-A")
    git(work, "commit", "-qm", "one")
    git(work, "tag", "beta")            # the rolling channel tag
    git(work, "remote", "add", "origin", str(origin))
    git(work, "push", "-q", "origin", "main", "--tags")

    subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True)
    git(clone, "config", "user.email", "t@example.com")
    git(clone, "config", "user.name", "t")

    # a new beta is published: the tag moves to a new commit
    (work / "f").write_text("2")
    git(work, "commit", "-qam", "two")
    git(work, "tag", "-f", "beta")
    git(work, "push", "-q", "--force", "origin", "main", "--tags")

    return origin, clone


class TestARollingTagBreaksAPlainFetch:
    """The behaviour the scripts were built on top of, stated once."""

    def test_a_plain_tag_fetch_fails_once_the_tag_has_moved(self, remote_and_clone):
        _, clone = remote_and_clone

        result = git(clone, "fetch", "--tags", "origin")

        assert result.returncode != 0
        assert "would clobber existing tag" in result.stderr

    def test_the_network_is_not_the_problem(self, remote_and_clone):
        """The same fetch without --tags succeeds, so nothing is unreachable."""
        _, clone = remote_and_clone

        assert git(clone, "fetch", "origin").returncode == 0

    def test_forcing_it_is_what_works(self, remote_and_clone):
        _, clone = remote_and_clone

        assert git(clone, "fetch", "--tags", "--force", "origin").returncode == 0

    def test_and_the_local_tag_then_matches_the_remote(self, remote_and_clone):
        origin, clone = remote_and_clone
        git(clone, "fetch", "--tags", "--force", "origin")

        local = git(clone, "rev-parse", "beta").stdout.strip()
        remote = git(origin, "rev-parse", "beta").stdout.strip()

        assert local == remote


# Every script that fetches tags, and whether it can survive a moved one. The
# release path is the one that matters most: ship.sh treats the failure as
# fatal, and rollback.sh is the emergency path, which must not be the thing
# that fails in an emergency.
TAG_FETCHERS = ["ship.sh", "promote.sh", "rollback.sh"]


@pytest.mark.parametrize("script", TAG_FETCHERS)
def test_every_tag_fetch_can_survive_a_rolling_tag(script):
    """A guard against this returning quietly on the next script that fetches."""
    text = (SCRIPTS / script).read_text()

    for line in text.splitlines():
        stripped = line.strip()
        if not re.search(r"\bgit fetch\b", stripped) or "--tags" not in stripped:
            continue
        if stripped.startswith("#"):
            continue
        assert "--force" in stripped or "-f " in stripped, (
            f"{script}: `{stripped}` fetches tags without --force, so it will "
            f"fail as soon as the beta or nightly tag is republished"
        )


def test_ship_does_not_refuse_a_tag_beta_already_cut():
    """Beta creates vX.Y.Z when it builds; promoting reuses that exact tag.

    release.yml says so in its own header. A guard that failed whenever the tag
    existed therefore fired on every promotion the script exists to perform,
    which is part of why stable sat at v2.1.9 while beta went to 2.1.18.
    """
    text = (SCRIPTS / "ship.sh").read_text()

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "rev-parse" not in stripped:
            continue
        if "fail " in stripped and "already exists" in stripped:
            raise AssertionError(
                f"ship.sh refuses an existing tag: `{stripped}`. Beta cuts the "
                f"tag first, so this blocks every promotion."
            )
