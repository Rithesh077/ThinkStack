"""What a new document starts as.

Scribe is a LaTeX editor that happens to live inside a research application.
Someone opening it to write a letter or a CV is not doing something unusual, and
the research-paper skeleton -- abstract, methodology, results -- is noise for
them. These tests hold the template set to the two promises the interface makes
about it: every template produces a document that compiles, and asking for one
that does not exist still gets you a document.
"""

import pytest

from domain.paper_writer import compiler, templates as T


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(compiler, "PAPERS_DIR", tmp_path / "papers_ws")
    return tmp_path


class TestTemplateSet:
    def test_every_template_is_a_complete_document(self):
        # The picker offers these by name; each has to stand on its own.
        for t in T.ALL:
            src = T.render(t.id, "A Title")
            assert r"\documentclass" in src, f"{t.id} has no class"
            assert r"\begin{document}" in src, f"{t.id} never opens"
            assert r"\end{document}" in src, f"{t.id} never closes"

    def test_ids_are_unique(self):
        ids = [t.id for t in T.ALL]
        assert len(ids) == len(set(ids))

    def test_default_is_one_of_them(self):
        assert T.DEFAULT in {t.id for t in T.ALL}

    def test_every_template_is_labelled(self):
        # A blank <option> is a picker you cannot use. This is the assertion
        # that would have caught the route sending `label` while the interface
        # read `name`.
        for t in T.ALL:
            assert t.label.strip(), f"{t.id} has no label"
            assert t.description.strip(), f"{t.id} has no description"


class TestUnknownIds:
    """A stale or misspelled id must not cost you the document."""

    @pytest.mark.parametrize("bad", [None, "", "nonsense", "PAPER", "../etc"])
    def test_unknown_id_falls_back_to_the_paper(self, bad):
        assert T.get(bad).id == T.PAPER.id

    def test_unknown_id_still_renders(self, bad="nonsense"):
        assert r"\documentclass" in T.render(bad, "T")


class TestTitleHandling:
    def test_title_reaches_the_document(self):
        assert "Cache Coherence" in T.render("paper", "Cache Coherence")

    def test_untitled_when_the_name_is_empty(self):
        assert "Untitled" in T.render("paper", "")

    @pytest.mark.parametrize("raw", ["R&D", "a_b", "50% faster", "back\\slash"])
    def test_tex_special_characters_do_not_break_the_preamble(self, raw):
        # A project named "R&D" must not produce a document that dies on its
        # own title. The name comes from a text field; it is not LaTeX.
        src = T.render("paper", raw)
        assert r"\begin{document}" in src


class TestCreateProjectUsesTemplates:
    def test_create_project_returns_rendered_source_not_the_id(self, workspace):
        # Regression: this returned the template ID, so `source` was None on
        # every default create and the editor opened empty.
        proj = compiler.create_project("Thesis", None)
        assert proj["source"] is not None
        assert r"\documentclass" in proj["source"]
        assert proj["template"] == T.DEFAULT

    def test_create_project_honours_the_choice(self, workspace):
        proj = compiler.create_project("To the editor", "letter")
        assert proj["template"] == "letter"
        assert proj["source"] == T.render("letter", "To the editor")

    def test_choice_is_written_to_disk(self, workspace):
        import json
        proj = compiler.create_project("CV", "cv")
        meta = compiler._get_project_dir(proj["project_id"]) / "meta.json"
        assert json.loads(meta.read_text())["template"] == "cv"

    def test_source_on_disk_matches_what_was_returned(self, workspace):
        proj = compiler.create_project("Report", "report")
        assert compiler.get_source(proj["project_id"]) == proj["source"]
