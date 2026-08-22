"""A linked file must be usable by the compile, not merely remembered.

Linking records where a file IS rather than taking a copy. Until 2026-08-23
that was bookkeeping and nothing else: Tectonic runs with the project as its
working directory, so a linked figure was invisible to the engine and
`\\includegraphics{chart.png}` failed on a file the panel listed as present.
The only thing that worked was typing an absolute path -- which works whether
or not the file was ever linked, and breaks the moment it moves, which is the
exact thing linking exists to survive.

The mechanism is Tectonic's `-Z search-path`, NOT the TEXINPUTS environment
variable. Tectonic has its own IO layer and ignores TEXINPUTS outright;
verified against the bundled 0.15.0, where the same document fails with
TEXINPUTS set and compiles with the flag. TEXINPUTS is still set for the
pdflatex fallback, which does read it.

These tests do not run an engine. They assert what the engine is ASKED, which
is the part that regressed and the part a machine with no LaTeX can check.
"""

from __future__ import annotations

import pytest

from domain.paper_writer import compiler, links as L


@pytest.fixture
def project(tmp_path):
    d = tmp_path / "proj"
    d.mkdir()
    (d / "main.tex").write_text("x")
    return d


@pytest.fixture
def outside(tmp_path):
    d = tmp_path / "elsewhere"
    d.mkdir()
    return d


class TestWhichDirectoriesAreOffered:
    def test_a_linked_file_contributes_its_parent(self, project, outside):
        f = outside / "chart.png"
        f.write_bytes(b"x")
        L.add_link(project, f)
        assert compiler._link_search_paths(project) == [outside.resolve()]

    def test_a_linked_folder_contributes_itself(self, project, outside):
        figures = outside / "figures"
        figures.mkdir()
        L.add_link(project, figures)
        # This is what makes a shared figures/ directory work: the document
        # says \includegraphics{plot.png}, not figures/plot.png.
        assert compiler._link_search_paths(project) == [figures.resolve()]

    def test_a_project_with_no_links_offers_nothing(self, project):
        assert compiler._link_search_paths(project) == []

    def test_two_files_in_one_folder_offer_it_once(self, project, outside):
        for n in ("a.png", "b.png"):
            (outside / n).write_bytes(b"x")
            L.add_link(project, outside / n)
        # A duplicated search path is not wrong, but it is a longer command
        # line for every compile and it makes the argv hard to read in a log.
        assert compiler._link_search_paths(project) == [outside.resolve()]

    def test_a_missing_link_is_skipped_not_fatal(self, project, outside):
        f = outside / "gone.png"
        f.write_bytes(b"x")
        L.add_link(project, f)
        f.unlink()
        # The panel already reports this one as missing. A compile that
        # refused to start because of it would be a worse answer than one
        # that runs and reports what it could not find.
        assert compiler._link_search_paths(project) == []

    def test_an_unreadable_links_file_does_not_stop_a_compile(self, project):
        (project / "links.json").write_text("{ not json")
        assert compiler._link_search_paths(project) == []


class TestWhatTheEngineIsAsked:
    """The flag has to actually reach the command line."""

    def _argv(self, monkeypatch, project, kind, engine="tectonic"):
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd
            seen["env"] = kw.get("env") or {}
            class R:
                returncode, stdout, stderr = 0, "", ""
            return R()

        monkeypatch.setattr(compiler.subprocess, "run", fake_run)
        compiler._run_engine(engine, kind, project / "main.tex", project)
        return seen

    def test_tectonic_is_given_the_search_path(self, project, outside, monkeypatch):
        (outside / "chart.png").write_bytes(b"x")
        L.add_link(project, outside / "chart.png")
        cmd = self._argv(monkeypatch, project, "tectonic")["cmd"]
        assert f"search-path={outside.resolve()}" in cmd

    def test_tectonic_keeps_its_other_flags(self, project, outside, monkeypatch):
        (outside / "chart.png").write_bytes(b"x")
        L.add_link(project, outside / "chart.png")
        cmd = self._argv(monkeypatch, project, "tectonic")["cmd"]
        # synctex feeds the position map, continue-on-errors is what makes a
        # mid-edit document still produce a PDF. Neither may be displaced.
        assert "--synctex" in cmd
        assert "continue-on-errors" in cmd

    def test_no_links_means_no_search_path_flag(self, project, monkeypatch):
        cmd = self._argv(monkeypatch, project, "tectonic")["cmd"]
        assert not any(str(a).startswith("search-path=") for a in cmd)

    def test_tectonic_is_not_given_TEXINPUTS_as_the_mechanism(
            self, project, outside, monkeypatch):
        (outside / "chart.png").write_bytes(b"x")
        L.add_link(project, outside / "chart.png")
        env = self._argv(monkeypatch, project, "tectonic")["env"]
        # Recorded because it is the mistake worth not repeating: setting this
        # and believing it worked is exactly how the feature could look fixed
        # while still failing. Tectonic ignores it.
        assert outside.name not in env.get("TEXINPUTS", "")

    def test_the_fallback_engine_gets_TEXINPUTS(self, project, outside, monkeypatch):
        (outside / "chart.png").write_bytes(b"x")
        L.add_link(project, outside / "chart.png")
        env = self._argv(monkeypatch, project, "pdflatex", engine="pdflatex")["env"]
        assert str(outside.resolve()) in env["TEXINPUTS"]

    def test_the_fallback_TEXINPUTS_still_extends_the_default(
            self, project, outside, monkeypatch):
        (outside / "chart.png").write_bytes(b"x")
        L.add_link(project, outside / "chart.png")
        env = self._argv(monkeypatch, project, "pdflatex", engine="pdflatex")["env"]
        # The trailing empty entry is load-bearing. Without it this REPLACES
        # the default search path, and the document loses the standard classes
        # and packages rather than gaining a figure.
        assert env["TEXINPUTS"].endswith(":")
