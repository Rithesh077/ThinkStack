"""What the Library dashboard reads: the two counts, and correcting a title.

Both were added because the page was lying in a quiet way -- two stat cards
were hardcoded to "-", and a wrong extracted title could not be repaired
anywhere in the app.
"""

import pytest
from fastapi import HTTPException

from api import routes_documents
from api.routes_documents import list_documents, rename_document
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


class TestRename:
    async def test_updates_every_chunk(self, monkeypatch):
        """The title is copied onto each chunk so a search hit can name its
        paper. Miss one and the same document answers to two titles depending
        on which passage matched."""
        seen = {}
        monkeypatch.setattr(
            routes_documents, "update_document_metadata_field",
            lambda doc_id, field, value: seen.update(
                {"doc": doc_id, "field": field, "value": value}) or 7,
        )

        result = await rename_document("docX", routes_documents.TitleUpdate(
            title="  Attention Is All You Need  "))

        assert seen == {"doc": "docX", "field": "title",
                        "value": "Attention Is All You Need"}
        assert result["chunks_updated"] == 7

    async def test_unknown_document_is_a_404(self, monkeypatch):
        monkeypatch.setattr(routes_documents, "update_document_metadata_field",
                            lambda *a: 0)

        with pytest.raises(HTTPException) as e:
            await rename_document("nope", routes_documents.TitleUpdate(title="x y"))
        assert e.value.status_code == 404

    @pytest.mark.parametrize("title", ["", "   ", "\n"])
    async def test_blank_titles_are_refused(self, title):
        """An empty title is what the old extractor's guard tested for and
        never saw. It must not become storable by hand either."""
        with pytest.raises(HTTPException) as e:
            await rename_document("docX", routes_documents.TitleUpdate(title=title))
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

        count = repo.update_document_metadata_field("docX", "title", "new")

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
        assert repo.update_document_metadata_field("nope", "title", "x") == 0
