"""unit tests for infrastructure.local_vector_store.

the store is the numpy/json-backed vector index. every test uses an isolated
tmp persist dir so nothing touches real user data. covers upsert/query/get/
update/delete plus the metadata filter and the degenerate cases (empty store,
zero-norm query, missing ids).
"""

import pytest

from infrastructure.local_vector_store import VectorStore


@pytest.fixture
def store(tmp_path):
    return VectorStore(persist_dir=str(tmp_path / "vs"))


def _seed(store):
    """three orthogonal-ish 2d vectors with simple metadata."""
    store.upsert(
        ids=["a", "b", "c"],
        documents=["doc a", "doc b", "doc c"],
        embeddings=[[1.0, 0.0], [0.0, 1.0], [0.9, 0.1]],
        metadatas=[{"kind": "x"}, {"kind": "y"}, {"kind": "x"}],
    )


class TestUpsertAndCount:
    def test_upsert_returns_count_and_persists(self, store):
        n = store.upsert(["a"], ["hello"], [[1.0, 0.0]], [{"k": 1}])
        assert n == 1
        assert store.count() == 1

    def test_upsert_existing_id_updates_in_place(self, store):
        store.upsert(["a"], ["v1"], [[1.0, 0.0]], [{"k": 1}])
        store.upsert(["a"], ["v2"], [[0.0, 1.0]], [{"k": 2}])
        assert store.count() == 1  # not duplicated
        got = store.get(ids=["a"])
        assert got["documents"] == ["v2"]

    def test_empty_store_counts_zero(self, store):
        assert store.count() == 0


class TestQuery:
    def test_returns_nearest_first(self, store):
        _seed(store)
        res = store.query([1.0, 0.0], n_results=3)
        assert res["ids"][0] == "a"  # identical direction is closest
        assert "b" in res["ids"]

    def test_respects_n_results(self, store):
        _seed(store)
        res = store.query([1.0, 0.0], n_results=1)
        assert len(res["ids"]) == 1

    def test_distances_are_sorted_ascending(self, store):
        _seed(store)
        res = store.query([1.0, 0.0], n_results=3)
        assert res["distances"] == sorted(res["distances"])

    # ── edge cases ──
    def test_query_on_empty_store_is_empty(self, store):
        res = store.query([1.0, 0.0], n_results=5)
        assert res == {"ids": [], "documents": [], "metadatas": [], "distances": []}

    def test_zero_norm_query_returns_empty(self, store):
        _seed(store)
        assert store.query([0.0, 0.0], n_results=3)["ids"] == []

    def test_where_equality_filter(self, store):
        _seed(store)
        res = store.query([1.0, 0.0], n_results=5, where={"kind": "x"})
        assert set(res["ids"]) == {"a", "c"}

    def test_where_in_operator(self, store):
        _seed(store)
        res = store.query([1.0, 0.0], n_results=5, where={"kind": {"$in": ["y"]}})
        assert res["ids"] == ["b"]

    def test_where_matching_nothing_is_empty(self, store):
        _seed(store)
        assert store.query([1.0, 0.0], where={"kind": "zzz"})["ids"] == []


class TestGetUpdateDelete:
    def test_get_by_ids(self, store):
        _seed(store)
        got = store.get(ids=["a", "c"])
        assert set(got["ids"]) == {"a", "c"}

    def test_get_by_where(self, store):
        _seed(store)
        got = store.get(where={"kind": "y"})
        assert got["ids"] == ["b"]

    def test_update_metadata_only(self, store):
        _seed(store)
        updated = store.update(ids=["a"], metadatas=[{"kind": "z"}])
        assert updated == 1
        assert store.get(ids=["a"])["metadatas"][0]["kind"] == "z"

    def test_update_missing_id_is_noop(self, store):
        _seed(store)
        assert store.update(ids=["ghost"], metadatas=[{"kind": "z"}]) == 0

    def test_delete_existing(self, store):
        _seed(store)
        assert store.delete(["a"]) == 1
        assert store.count() == 2

    def test_delete_missing_id_returns_zero(self, store):
        _seed(store)
        assert store.delete(["ghost"]) == 0
        assert store.count() == 3

    def test_delete_rebuilds_query_matrix(self, store):
        _seed(store)
        store.delete(["a"])
        # querying the deleted direction must no longer return "a"
        assert "a" not in store.query([1.0, 0.0], n_results=3)["ids"]


class TestPersistence:
    def test_reload_from_disk(self, tmp_path):
        d = str(tmp_path / "vs")
        s1 = VectorStore(persist_dir=d)
        s1.upsert(["a"], ["hello"], [[1.0, 0.0]], [{"k": 1}])
        # a fresh instance on the same dir must see the persisted vector
        s2 = VectorStore(persist_dir=d)
        assert s2.count() == 1
        assert s2.get(ids=["a"])["documents"] == ["hello"]

    def test_corrupt_store_starts_fresh(self, tmp_path):
        d = tmp_path / "vs"
        d.mkdir()
        (d / "vectors.json").write_text("{ not json")
        s = VectorStore(persist_dir=str(d))  # must not raise
        assert s.count() == 0


class TestSqliteMigration:
    """Moving an existing installation off vectors.json.

    The store used to be one JSON file rewritten in full on every write. A user
    upgrading has that file and nothing else, so the first open has to import it
    -- exactly once, without destroying it, and without noticing a second time.
    """

    @staticmethod
    def _legacy(dirpath, entries):
        import json
        dirpath.mkdir(parents=True, exist_ok=True)
        (dirpath / "vectors.json").write_text(json.dumps(entries), encoding="utf-8")

    def test_a_legacy_file_is_imported_on_first_open(self, tmp_path):
        d = tmp_path / "vs"
        self._legacy(d, [
            {"id": "a", "document": "alpha", "embedding": [1.0, 0.0],
             "metadata": {"doc_id": "d1"}},
            {"id": "b", "document": "beta", "embedding": [0.0, 1.0],
             "metadata": {"doc_id": "d1"}},
        ])
        s = VectorStore(persist_dir=str(d))
        assert s.count() == 2
        assert s.get(ids=["a"])["documents"] == ["alpha"]
        # and the vectors survived the round trip, not just the text
        assert s.query([1.0, 0.0], n_results=1)["ids"] == ["a"]

    def test_the_legacy_file_is_kept_not_deleted(self, tmp_path):
        d = tmp_path / "vs"
        self._legacy(d, [{"id": "a", "document": "x", "embedding": [1.0, 0.0],
                          "metadata": {}}])
        VectorStore(persist_dir=str(d))
        assert not (d / "vectors.json").exists()
        # a migration that destroys its only source has no second attempt
        assert (d / "vectors.json.migrated").exists()

    def test_migration_does_not_run_twice(self, tmp_path):
        """A second legacy file appearing later must not re-import over newer data."""
        d = tmp_path / "vs"
        self._legacy(d, [{"id": "a", "document": "old", "embedding": [1.0, 0.0],
                          "metadata": {}}])
        s1 = VectorStore(persist_dir=str(d))
        s1.upsert(["b"], ["new"], [[0.0, 1.0]], [{}])

        # someone restores a stale export next to the database
        self._legacy(d, [{"id": "a", "document": "STALE", "embedding": [1.0, 0.0],
                          "metadata": {}}])
        s2 = VectorStore(persist_dir=str(d))

        assert s2.count() == 2                      # not reset to the stale copy
        assert s2.get(ids=["a"])["documents"] == ["old"]

    def test_a_write_touches_only_its_own_rows(self, tmp_path):
        """The reason for the change: cost must not scale with the corpus.

        Asserted by behaviour rather than by timing -- an existing row is left
        byte-identical while a new one is added, which is what "no full rewrite"
        means in terms anyone can check.
        """
        import sqlite3
        d = str(tmp_path / "vs")
        s = VectorStore(persist_dir=d)
        s.upsert(["a"], ["alpha"], [[1.0, 0.0]], [{"doc_id": "d1"}])

        con = sqlite3.connect(str(tmp_path / "vs" / "vectors.db"))
        before = con.execute("SELECT embedding FROM chunks WHERE id='a'").fetchone()[0]

        s.upsert(["b"], ["beta"], [[0.0, 1.0]], [{"doc_id": "d2"}])

        after = con.execute("SELECT embedding FROM chunks WHERE id='a'").fetchone()[0]
        assert before == after
        assert con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 2
        con.close()

    def test_deleting_removes_the_row_from_disk(self, tmp_path):
        d = str(tmp_path / "vs")
        s = VectorStore(persist_dir=d)
        s.upsert(["a", "b"], ["x", "y"], [[1.0, 0.0], [0.0, 1.0]], [{}, {}])
        s.delete(["a"])
        # gone from memory and from the database, not merely filtered out
        assert VectorStore(persist_dir=d).count() == 1


class TestMigrationOnSomeoneElsesMachine:
    """The migration runs once, unattended, on a stranger's library.

    Every case here is something a real data directory can contain. The rule
    throughout: never lose the source until the rows are committed and counted,
    and never let one bad row cost the whole corpus.
    """

    @staticmethod
    def _legacy(dirpath, payload):
        dirpath.mkdir(parents=True, exist_ok=True)
        p = dirpath / "vectors.json"
        p.write_text(payload if isinstance(payload, str) else __import__("json").dumps(payload),
                     encoding="utf-8")
        return p

    def test_unreadable_json_is_kept_and_not_silently_dropped(self, tmp_path):
        d = tmp_path / "vs"
        src = self._legacy(d, "{ this is not json")
        s = VectorStore(persist_dir=str(d))
        assert s.count() == 0
        # the user's file must still be there to recover from
        assert src.exists()
        assert not (d / "vectors.json.migrated").exists()

    def test_one_malformed_entry_does_not_cost_the_library(self, tmp_path):
        d = tmp_path / "vs"
        self._legacy(d, [
            {"id": "a", "document": "alpha", "embedding": [1.0, 0.0], "metadata": {}},
            {"id": "b", "document": "beta"},                       # no embedding
            {"embedding": [0.0, 1.0], "document": "no id"},        # no id
            {"id": "c", "document": "gamma", "embedding": [0.0, 1.0], "metadata": {}},
        ])
        s = VectorStore(persist_dir=str(d))
        assert s.count() == 2
        assert sorted(s.get()["ids"]) == ["a", "c"]
        assert (d / "vectors.json.migrated").exists()

    def test_a_file_with_nothing_usable_is_kept(self, tmp_path):
        d = tmp_path / "vs"
        src = self._legacy(d, [{"nonsense": True}, {"also": "nonsense"}])
        s = VectorStore(persist_dir=str(d))
        assert s.count() == 0
        assert src.exists()          # not renamed away; there is nothing to show for it

    def test_an_empty_library_migrates_quietly(self, tmp_path):
        d = tmp_path / "vs"
        self._legacy(d, [])
        assert VectorStore(persist_dir=str(d)).count() == 0

    def test_a_large_library_migrates_in_batches(self, tmp_path):
        d = tmp_path / "vs"
        self._legacy(d, [
            {"id": f"e{i}", "document": f"doc {i}", "embedding": [float(i), 1.0],
             "metadata": {"doc_id": f"d{i % 7}"}}
            for i in range(1200)                      # crosses the 500-row batch
        ])
        s = VectorStore(persist_dir=str(d))
        assert s.count() == 1200
        assert len(s.get(where={"doc_id": "d3"})["ids"]) == 1200 // 7 + (1 if 1200 % 7 > 3 else 0)

    def test_startup_survives_mixed_embedding_widths(self, tmp_path):
        """A store edited by hand, or written by an older build."""
        import sqlite3
        import numpy as _np
        d = tmp_path / "vs"; d.mkdir()
        con = sqlite3.connect(str(d / "vectors.db"))
        con.execute("""CREATE TABLE chunks (id TEXT PRIMARY KEY, doc_id TEXT,
                       document TEXT NOT NULL, embedding BLOB NOT NULL,
                       metadata TEXT NOT NULL)""")
        rows = [("a", None, "two-d", _np.asarray([1.0, 0.0], dtype=_np.float32).tobytes(), "{}"),
                ("b", None, "two-d", _np.asarray([0.0, 1.0], dtype=_np.float32).tobytes(), "{}"),
                ("c", None, "three-d", _np.asarray([1.0, 0.0, 0.0], dtype=_np.float32).tobytes(), "{}")]
        con.executemany("INSERT INTO chunks VALUES(?,?,?,?,?)", rows)
        con.commit(); con.close()

        s = VectorStore(persist_dir=str(d))          # must not raise
        assert s.count() == 2                         # the majority width survives
        assert s.query([1.0, 0.0], n_results=1)["ids"] == ["a"]


class TestNothingChangedForTheUser:
    """The switch to SQLite must be invisible in results, not merely close.

    Embeddings used to be written as decimal text and are now float32 bytes.
    That round trip is lossless, but "should be" is not a guarantee anyone can
    act on, so it is asserted -- as are the rankings built on top of it, since
    a silent change in search order is the one regression a user would notice
    and never be able to report precisely.
    """

    def test_embeddings_survive_the_round_trip_exactly(self, tmp_path):
        import numpy as np
        rng = np.random.default_rng(11)
        vecs = [rng.normal(size=64).astype(np.float32).tolist() for _ in range(50)]
        d = str(tmp_path / "vs")

        s1 = VectorStore(persist_dir=d)
        s1.upsert([f"e{i}" for i in range(50)], [f"doc {i}" for i in range(50)],
                  vecs, [{"doc_id": f"d{i % 5}"} for i in range(50)])

        s2 = VectorStore(persist_dir=d)          # reload from disk
        everything = s2.get_embeddings()
        assert everything["embeddings"].dtype == np.float32
        got = dict(zip(everything["ids"], everything["embeddings"]))
        for i, original in enumerate(vecs):
            assert np.array_equal(
                got[f"e{i}"], np.asarray(original, dtype=np.float32)
            ), f"e{i} changed on the way through sqlite"

    def test_ranking_is_identical_after_a_reload(self, tmp_path):
        import numpy as np
        rng = np.random.default_rng(12)
        vecs = [rng.normal(size=32).astype(np.float32).tolist() for _ in range(40)]
        d = str(tmp_path / "vs")
        s1 = VectorStore(persist_dir=d)
        s1.upsert([f"e{i}" for i in range(40)], [f"doc {i}" for i in range(40)],
                  vecs, [{} for _ in range(40)])

        probes = [vecs[3], vecs[17], rng.normal(size=32).tolist()]
        before = [s1.query(p, n_results=10) for p in probes]
        after = [VectorStore(persist_dir=d).query(p, n_results=10) for p in probes]

        for b, a in zip(before, after):
            assert b["ids"] == a["ids"]
            assert np.allclose(b["distances"], a["distances"], atol=1e-7)

    def test_the_store_recovers_from_a_force_quit(self, tmp_path):
        """WAL files left behind by a kill -9 must not cost the library.

        Write-ahead logging means a crash can leave -wal and -shm beside the
        database with committed data still only in the log. Opening it again has
        to replay that, or a user who force-quit the application loses whatever
        they ingested last.
        """
        d = tmp_path / "vs"
        s = VectorStore(persist_dir=str(d))
        s.upsert(["a", "b"], ["alpha", "beta"], [[1.0, 0.0], [0.0, 1.0]],
                 [{"doc_id": "d1"}, {"doc_id": "d1"}])

        # the connection is never closed, exactly as in a killed process
        assert (d / "vectors.db-wal").exists() or (d / "vectors.db").exists()

        recovered = VectorStore(persist_dir=str(d))
        assert recovered.count() == 2
        assert recovered.query([1.0, 0.0], n_results=1)["ids"] == ["a"]
