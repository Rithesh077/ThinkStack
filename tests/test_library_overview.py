"""What the Library dashboard reads: the two counts, and correcting a title.

Both were added because the page was lying in a quiet way -- two stat cards
were hardcoded to "-", and a wrong extracted title could not be repaired
anywhere in the app.
"""

import pytest
from fastapi import HTTPException

from api import routes_documents
from api.routes_documents import list_documents, correct_reference
from domain.knowledge_base.author_codec import decode_authors
from domain.knowledge_base import repository as repo
from infrastructure.analysis_cache import DocAnalysisCache


class TestAnalysisCount:
    def test_counts_documents_not_fields(self, tmp_path):
        cache = DocAnalysisCache(tmp_path / "a.json")
        cache.put("a", summary="s", claims=[{"c": 1}])
        cache.put("b", summary="s2", claims=[])
        assert cache.count() == 2

    def test_a_half_filled_entry_still_counts(self, tmp_path):
        """`merge` creates an entry the moment claims arrive, before the
        summary does. That document has been analysed."""
        cache = DocAnalysisCache(tmp_path / "a.json")
        cache.merge("a", claims=[{"c": 1}])
        assert cache.count() == 1

    def test_an_empty_entry_does_not(self, tmp_path):
        cache = DocAnalysisCache(tmp_path / "a.json")
        cache.merge("a", claims=[])
        assert cache.count() == 0

    def test_empty_cache(self, tmp_path):
        assert DocAnalysisCache(tmp_path / "a.json").count() == 0


class TestListCounts:
    async def test_gaps_is_the_newest_run_not_a_running_total(self, monkeypatch):
        """A gap scan covers the whole library and supersedes the one before
        it. Summing every run counts the same gap once per rescan, so the
        number would only ever climb."""
        monkeypatch.setattr(routes_documents, "list_stored_pdfs", lambda: [])
        monkeypatch.setattr(routes_documents, "get_collection_stats",
                            lambda: {"total_chunks": 0})

        class FakeHistory:
            # RunHistoryStore.list() is newest first.
            def list(self):
                return [{"total_gaps": 4}, {"total_gaps": 11}, {"total_gaps": 7}]

        monkeypatch.setattr(routes_documents, "gap_history", FakeHistory())
        monkeypatch.setattr(routes_documents.doc_analysis_cache, "count", lambda: 3)

        result = await list_documents()

        assert result["gaps"] == 4, "newest run, not 22"
        assert result["analyses"] == 3

    async def test_no_history_yet_reports_zero(self, monkeypatch):
        monkeypatch.setattr(routes_documents, "list_stored_pdfs", lambda: [])
        monkeypatch.setattr(routes_documents, "get_collection_stats",
                            lambda: {"total_chunks": 0})
        monkeypatch.setattr(routes_documents, "gap_history",
                            type("H", (), {"list": lambda self: []})())
        monkeypatch.setattr(routes_documents.doc_analysis_cache, "count", lambda: 0)

        result = await list_documents()

        assert result["gaps"] == 0 and result["analyses"] == 0


class TestCorrectReference:
    """Repairing what the extractor got wrong.

    Titles are ~93% right and author lists ~86%, so about one paper in seven
    is stored under something wrong. It labels every node on the map, names
    every search hit, and is what a BibTeX entry is built from.
    """

    @staticmethod
    def _capture(monkeypatch, count=7):
        seen = {}
        monkeypatch.setattr(
            routes_documents, "update_document_metadata",
            lambda doc_id, fields: seen.update({"doc": doc_id, **fields}) or count,
        )
        return seen

    async def test_all_three_fields_go_in_one_write(self, monkeypatch):
        """Correcting a reference usually means fixing several fields at once,
        and each write touches every chunk of the paper."""
        seen = self._capture(monkeypatch)

        result = await correct_reference("docX", routes_documents.ReferenceUpdate(
            title="  Attention Is All You Need  ",
            authors=["Ashish Vaswani", "  ", "Noam Shazeer"],
            year=" 2017 ",
        ))

        assert seen["doc"] == "docX"
        assert seen["title"] == "Attention Is All You Need"
        assert seen["year"] == "2017"
        assert decode_authors(seen["authors"]) == ["Ashish Vaswani", "Noam Shazeer"]
        assert result["chunks_updated"] == 7

    async def test_an_omitted_field_is_left_alone(self, monkeypatch):
        """Fixing the authors must not blank the title."""
        seen = self._capture(monkeypatch)
        await correct_reference("docX", routes_documents.ReferenceUpdate(
            authors=["Ada Lovelace"]))
        assert set(seen) == {"doc", "authors"}

    async def test_authors_are_stored_so_bibtex_can_split_them(self, monkeypatch):
        """The whole reason for the codec: a comma is BibTeX syntax."""
        seen = self._capture(monkeypatch)
        await correct_reference("docX", routes_documents.ReferenceUpdate(
            authors=["Vaswani, Ashish"]))
        assert decode_authors(seen["authors"]) == ["Vaswani, Ashish"]

    async def test_unknown_document_is_a_404(self, monkeypatch):
        self._capture(monkeypatch, count=0)
        with pytest.raises(HTTPException) as e:
            await correct_reference("nope", routes_documents.ReferenceUpdate(title="x y"))
        assert e.value.status_code == 404

    @pytest.mark.parametrize("title", ["", "   ", "\n"])
    async def test_blank_titles_are_refused(self, title):
        """An empty title is what the old extractor's guard tested for and
        never saw. It must not become storable by hand either."""
        with pytest.raises(HTTPException) as e:
            await correct_reference("docX", routes_documents.ReferenceUpdate(title=title))
        assert e.value.status_code == 400

    async def test_a_blank_year_is_allowed(self, monkeypatch):
        """An unstated year is a fact the extractor reports honestly."""
        seen = self._capture(monkeypatch)
        await correct_reference("docX", routes_documents.ReferenceUpdate(year=""))
        assert seen["year"] == ""

    @pytest.mark.parametrize("year", ["17", "20177", "twenty", "2017a"])
    async def test_a_year_that_is_not_a_year_is_refused(self, year):
        with pytest.raises(HTTPException) as e:
            await correct_reference("docX", routes_documents.ReferenceUpdate(year=year))
        assert e.value.status_code == 400

    async def test_an_empty_patch_changes_nothing(self):
        with pytest.raises(HTTPException) as e:
            await correct_reference("docX", routes_documents.ReferenceUpdate())
        assert e.value.status_code == 400

    async def test_an_absurd_author_list_is_refused(self):
        with pytest.raises(HTTPException) as e:
            await correct_reference("docX", routes_documents.ReferenceUpdate(
                authors=[f"Author {i}" for i in range(200)]))
        assert e.value.status_code == 400


class TestUpdateEveryChunk:
    def test_writes_all_ids_in_one_call(self, monkeypatch):
        captured = {}

        class FakeStore:
            def get(self, where=None, ids=None):
                return {"ids": ["c1", "c2", "c3"],
                        "metadatas": [{"title": "old"} for _ in range(3)]}

            def update(self, ids, metadatas):
                captured["ids"] = ids
                captured["metadatas"] = metadatas

        monkeypatch.setattr(repo, "get_vector_store", lambda: FakeStore())

        count = repo.update_document_metadata("docX", {"title": "new"})

        assert count == 3
        assert captured["ids"] == ["c1", "c2", "c3"]
        assert all(m["title"] == "new" for m in captured["metadatas"])

    def test_unknown_document_writes_nothing(self, monkeypatch):
        class EmptyStore:
            def get(self, where=None, ids=None):
                return {"ids": [], "metadatas": []}

            def update(self, ids, metadatas):
                raise AssertionError("must not write when there is nothing to write")

        monkeypatch.setattr(repo, "get_vector_store", lambda: EmptyStore())
        assert repo.update_document_metadata("nope", {"title": "x"}) == 0
