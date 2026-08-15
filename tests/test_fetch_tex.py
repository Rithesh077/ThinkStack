"""The TeX cache warm-up, exercised against a stand-in engine.

Nothing is mocked at the Python level: each test writes a fake `tectonic` into
the destination, which makes the real script skip the download and go straight
to warming, and then runs `scripts/fetch-tex.sh` as a subprocess exactly the
way CI and `build.sh` run it.

This exists because of the macOS build of 2026-08-14. Tectonic fetches every
LaTeX package it needs from one CDN, and that CDN answered `429 Too Many
Requests`:

    warning: failure requesting "puenc.def" from network
    caused by: unexpected HTTP response code 429 Too Many Requests
    error: hyperref.sty:2461: ! LaTeX Error: File `puenc.def' not found.

Linux warmed its cache at 18:53:42 and macOS started at 18:53:52. Ten seconds
apart on the same rate limiter; Linux got through and macOS did not. Nothing
about the failure was specific to macOS -- it lost a race that the matrix
creates every time it runs.

The engine retries an individual file a few times and then gives up. There was
no retry around the compile itself, so one throttled file failed the whole
release.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "fetch-tex.sh"

# A fake engine, in place of the real download. `fetch-tex.sh` skips fetching
# when an executable already sits at the destination, which is the seam these
# tests use.
#
# It counts its own invocations in a file so a test can say "fail twice, then
# work", which is exactly the shape of a transient rate limit.
FAKE_ENGINE = r"""#!/bin/bash
COUNT_FILE="{count_file}"
FAIL_TIMES={fail_times}

n=$(cat "$COUNT_FILE" 2>/dev/null || echo 0)
n=$((n + 1))
echo "$n" > "$COUNT_FILE"

# --outdir <dir> is where the real engine writes warm.pdf
outdir=""
prev=""
for arg in "$@"; do
    [ "$prev" = "--outdir" ] && outdir="$arg"
    prev="$arg"
done

# Partially populate the cache even on failure, the way the real engine does:
# it downloads what it can before the throttled file stops it.
mkdir -p "$TECTONIC_CACHE_DIR/files"
echo "partial" > "$TECTONIC_CACHE_DIR/files/etexcmds.sty"

if [ "$n" -le "$FAIL_TIMES" ]; then
    echo 'warning: failure requesting "puenc.def" from network' >&2
    echo 'caused by: unexpected HTTP response code 429 Too Many Requests' >&2
    echo "error: hyperref.sty:2461: ! LaTeX Error: File \`puenc.def' not found." >&2
    exit 1
fi

echo "%PDF-1.5 warmed" > "$outdir/warm.pdf"
echo "note: cache warmed"
exit 0
"""


@pytest.fixture()
def dest(tmp_path: Path) -> Path:
    return tmp_path / "tex"


def install_fake_engine(dest: Path, tmp_path: Path, fail_times: int) -> Path:
    """Put a stand-in engine where the script expects the real one."""
    dest.mkdir(parents=True, exist_ok=True)
    binary = dest / ("tectonic.exe" if os.name == "nt" else "tectonic")
    count_file = tmp_path / "invocations"
    binary.write_text(
        FAKE_ENGINE.format(count_file=count_file, fail_times=fail_times)
    )
    binary.chmod(0o755)
    return count_file


def run(dest: Path, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), str(dest)],
        capture_output=True,
        text=True,
        timeout=timeout,
        # keeps the test quick: the script reads this for its backoff
        env={**os.environ, "TEX_WARM_RETRY_DELAY": "0"},
    )


def invocations(count_file: Path) -> int:
    return int(count_file.read_text().strip()) if count_file.exists() else 0


class TestTransientThrottling:
    """A 429 is temporary. The build must not end because of one."""

    def test_a_single_throttled_attempt_is_retried(self, dest, tmp_path):
        count_file = install_fake_engine(dest, tmp_path, fail_times=1)

        result = run(dest)

        assert result.returncode == 0, result.stdout + result.stderr
        assert invocations(count_file) == 2
        assert (dest / "cache").is_dir()

    def test_it_keeps_trying_past_a_second_failure(self, dest, tmp_path):
        count_file = install_fake_engine(dest, tmp_path, fail_times=2)

        result = run(dest)

        assert result.returncode == 0, result.stdout + result.stderr
        assert invocations(count_file) == 3

    def test_the_retry_is_reported_rather_than_hidden(self, dest, tmp_path):
        install_fake_engine(dest, tmp_path, fail_times=1)

        result = run(dest)

        combined = result.stdout + result.stderr
        assert "retry" in combined.lower() or "again" in combined.lower()


class TestARealFailureStillStopsTheBuild:
    """The guard is deliberate and must survive the retry being added.

    Shipping an installer with an empty cache means the paper writer cannot
    compile on a user's machine, which is the reason the engine is bundled.
    """

    def test_an_engine_that_never_succeeds_fails_the_build(self, dest, tmp_path):
        count_file = install_fake_engine(dest, tmp_path, fail_times=99)

        result = run(dest)

        assert result.returncode != 0
        assert invocations(count_file) > 1, "it should have tried more than once"

    def test_the_engine_output_is_shown_on_final_failure(self, dest, tmp_path):
        install_fake_engine(dest, tmp_path, fail_times=99)

        result = run(dest)

        combined = result.stdout + result.stderr
        assert "puenc.def" in combined, "the real error has to reach the log"
        assert "Refusing to continue" in combined


class TestAPartialCacheIsNotAWarmCache:
    """The failure leaves files behind, and they must not look like success.

    The early exit used to accept any non-empty cache directory. A throttled
    run writes some of the packages before it stops, so on a machine where the
    directory survives -- a developer running build.sh again -- the next build
    would skip warming and bundle a cache missing whatever came after the file
    that was throttled.
    """

    def test_a_partial_cache_is_rewarmed_rather_than_trusted(self, dest, tmp_path):
        dest.mkdir(parents=True)
        (dest / "cache" / "files").mkdir(parents=True)
        (dest / "cache" / "files" / "etexcmds.sty").write_text("partial")
        count_file = install_fake_engine(dest, tmp_path, fail_times=0)

        result = run(dest)

        assert result.returncode == 0, result.stdout + result.stderr
        assert invocations(count_file) >= 1, "a partial cache must not be trusted"

    def test_a_cache_a_previous_run_proved_is_reused(self, dest, tmp_path):
        count_file = install_fake_engine(dest, tmp_path, fail_times=0)

        first = run(dest)
        assert first.returncode == 0, first.stdout + first.stderr
        after_first = invocations(count_file)

        second = run(dest)

        assert second.returncode == 0, second.stdout + second.stderr
        assert invocations(count_file) == after_first, "it should not rewarm"
        assert "warm" in (second.stdout + second.stderr).lower()
