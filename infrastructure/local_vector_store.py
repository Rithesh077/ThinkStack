"""
vector store module.

Vectors live in SQLite; similarity search stays in numpy. Those are two
separate decisions and it is worth keeping them apart.

WHY NOT CHROMADB OR FAISS: both depend on compiled C++ extensions (hnswlib and
friends), which are the most fragile thing that can go into a PyInstaller
bundle built on three operating systems -- the component that works on two and
fails on the third, at a user's launch rather than at our build.

WHY SQLITE IS NOT THAT: it is compiled into CPython and reached through the
standard library. No wheel, no toolchain, no --hidden-import, nothing new for
the bundler to miss. The objection that rules out the alternatives does not
apply to it.

WHY NOT JSON, WHICH THIS USED TO BE: one file holding every chunk had to be
rewritten in full on every write and parsed in full at every start. Measured on
a real store, 464 chunks across 21 papers was 5.6MB, 54ms to parse and 70ms to
rewrite; the same shape at 500 papers is 133MB, 1.3s and 1.7s, and ingesting
the five-hundredth paper rewrote the previous four hundred and ninety-nine.
Building a library was quadratic in the number of papers. Here a write touches
only the rows it changes.

WHAT DID NOT CHANGE: the search. SQLite has no vector index and none is wanted.
Every embedding is held in one numpy matrix and a query is compared against all
of them, exactly as before -- deliberately exact rather than approximate, which
is affordable for a personal library and is the reason no ANN index appears
here.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

import numpy as np

from config import settings

logger = logging.getLogger(__name__)

_store_instance = None


class VectorStore:
    """file-backed vector store with numpy cosine similarity search."""

    def __init__(self, persist_dir: str = None):
        self.persist_dir = Path(persist_dir or str(settings.chroma_dir))
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._data_file = self.persist_dir / "vectors.json"   # legacy, migrated
        self._db_file = self.persist_dir / "vectors.db"
        self._entries = []
        self._embeddings = None
        self._connect()
        self._migrate_json_if_present()
        self._load()

    # ---------------------------------------------------------------- storage

    def _connect(self):
        """Open the database and make sure the schema is there.

        `check_same_thread=False` because the job queue writes from a worker
        while requests read on the event loop thread; access is serialised by
        the GIL around short statements, and WAL lets a reader proceed during a
        write rather than blocking on it.
        """
        self._con = sqlite3.connect(str(self._db_file), check_same_thread=False)
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.execute("PRAGMA synchronous=NORMAL")
        self._con.execute(
            """CREATE TABLE IF NOT EXISTS chunks (
                   id        TEXT PRIMARY KEY,
                   doc_id    TEXT,
                   document  TEXT NOT NULL,
                   embedding BLOB NOT NULL,
                   metadata  TEXT NOT NULL
               )"""
        )
        self._con.execute("CREATE INDEX IF NOT EXISTS ix_chunks_doc ON chunks(doc_id)")
        self._con.commit()

    def _migrate_json_if_present(self):
        """One-time import of the old vectors.json, then set it aside.

        Kept rather than deleted: an installation that downgrades should still
        find its data, and a migration that destroys its only source has no
        second attempt if it goes wrong.
        """
        if not self._data_file.exists():
            return
        if self._con.execute("SELECT 1 FROM chunks LIMIT 1").fetchone():
            return                      # already migrated; leave both alone
        try:
            entries = json.loads(self._data_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("could not read legacy vectors.json: %s", e)
            return
        if not entries:
            return
        self._write_rows(entries)
        self._data_file.rename(self._data_file.with_suffix(".json.migrated"))
        logger.info("migrated %d vectors from vectors.json into sqlite", len(entries))

    @staticmethod
    def _pack(embedding) -> bytes:
        return np.asarray(embedding, dtype=np.float32).tobytes()

    @staticmethod
    def _unpack(blob: bytes) -> list:
        return np.frombuffer(blob, dtype=np.float32).tolist()

    def _write_rows(self, entries: list[dict]):
        """Insert or replace exactly these entries. Nothing else is touched."""
        self._con.executemany(
            "INSERT OR REPLACE INTO chunks VALUES (?,?,?,?,?)",
            [
                (
                    e["id"],
                    (e.get("metadata") or {}).get("doc_id"),
                    e["document"],
                    self._pack(e["embedding"]),
                    json.dumps(e.get("metadata") or {}),
                )
                for e in entries
            ],
        )
        self._con.commit()

    def _load(self):
        """Read every row into memory, once, at startup.

        The whole corpus is held resident because that is what the search
        needs: one matrix, compared in full. Reading it back is a scan of a
        b-tree and a memoryview per blob, which is roughly an order of
        magnitude cheaper than parsing the equivalent JSON.
        """
        self._entries = []
        try:
            rows = self._con.execute(
                "SELECT id, document, embedding, metadata FROM chunks"
            ).fetchall()
        except sqlite3.DatabaseError as e:
            logger.warning("failed to read vector store, starting fresh: %s", e)
            self._embeddings = None
            return

        mat = []
        for entry_id, document, blob, meta in rows:
            vec = np.frombuffer(blob, dtype=np.float32)
            self._entries.append(
                {
                    "id": entry_id,
                    "document": document,
                    "embedding": vec.tolist(),
                    "metadata": json.loads(meta),
                }
            )
            mat.append(vec)

        self._embeddings = np.vstack(mat) if mat else None
        logger.info("loaded %d vectors from sqlite", len(self._entries))

    def _rebuild_matrix(self):
        """rebuild the numpy embedding matrix from entries."""
        if self._entries:
            self._embeddings = np.array(
                [e["embedding"] for e in self._entries],
                dtype=np.float32,
            )
        else:
            self._embeddings = None

    def upsert(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> int:
        """insert or update entries in the vector store.

        args:
            ids: unique identifiers for each entry.
            documents: text content for each entry.
            embeddings: embedding vectors for each entry.
            metadatas: metadata dictionaries for each entry.

        returns:
            number of entries upserted.
        """
        existing_ids = {e["id"]: i for i, e in enumerate(self._entries)}
        touched = []

        for entry_id, doc, emb, meta in zip(ids, documents, embeddings, metadatas):
            entry = {
                "id": entry_id,
                "document": doc,
                "embedding": emb if isinstance(emb, list) else emb.tolist(),
                "metadata": meta,
            }
            if entry_id in existing_ids:
                self._entries[existing_ids[entry_id]] = entry
            else:
                self._entries.append(entry)
            touched.append(entry)

        self._rebuild_matrix()
        # only the rows in this call are written. the cost of ingesting a paper
        # no longer depends on how many papers came before it.
        self._write_rows(touched)
        return len(ids)

    def update(
        self,
        ids: list[str],
        metadatas: Optional[list[dict]] = None,
    ) -> int:
        """update metadata for existing entries without changing documents/embeddings.

        args:
            ids: list of entry ids to update.
            metadatas: list of metadata dicts corresponding to the ids.

        returns:
            number of entries updated.
        """
        existing_ids = {e["id"]: i for i, e in enumerate(self._entries)}
        updated = 0

        if metadatas:
            for entry_id, meta in zip(ids, metadatas):
                if entry_id in existing_ids:
                    self._entries[existing_ids[entry_id]]["metadata"] = meta
                    updated += 1

        if updated > 0:
            self._con.executemany(
                "UPDATE chunks SET metadata = ?, doc_id = ? WHERE id = ?",
                [
                    (
                        json.dumps(self._entries[existing_ids[i]]["metadata"]),
                        (self._entries[existing_ids[i]]["metadata"] or {}).get("doc_id"),
                        i,
                    )
                    for i in ids
                    if i in existing_ids
                ],
            )
            self._con.commit()

        return updated

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        where: Optional[dict] = None,
    ) -> dict:
        """find the most similar entries using cosine similarity.

        args:
            query_embedding: the query vector to compare against.
            n_results: maximum number of results to return.
            where: optional metadata filter dict (supports simple equality
                   and $in operator).

        returns:
            dict with ids, documents, metadatas, and distances lists.
        """
        if not self._entries or self._embeddings is None:
            return {"ids": [], "documents": [], "metadatas": [], "distances": []}

        indices = list(range(len(self._entries)))
        if where:
            indices = self._apply_filter(indices, where)

        if not indices:
            return {"ids": [], "documents": [], "metadatas": [], "distances": []}

        filtered_embeddings = self._embeddings[indices]
        query_vec = np.array(query_embedding, dtype=np.float32)

        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return {"ids": [], "documents": [], "metadatas": [], "distances": []}

        embed_norms = np.linalg.norm(filtered_embeddings, axis=1)
        valid = embed_norms > 0
        similarities = np.zeros(len(filtered_embeddings))
        similarities[valid] = (
            filtered_embeddings[valid] @ query_vec
        ) / (embed_norms[valid] * query_norm)

        distances = 1.0 - similarities

        top_k = min(n_results, len(indices))
        top_indices = np.argsort(distances)[:top_k]

        result_ids = []
        result_docs = []
        result_metas = []
        result_dists = []

        for idx in top_indices:
            original_idx = indices[idx]
            entry = self._entries[original_idx]
            result_ids.append(entry["id"])
            result_docs.append(entry["document"])
            result_metas.append(entry["metadata"])
            result_dists.append(float(distances[idx]))

        return {
            "ids": result_ids,
            "documents": result_docs,
            "metadatas": result_metas,
            "distances": result_dists,
        }

    def get(
        self,
        where: Optional[dict] = None,
        ids: Optional[list[str]] = None,
    ) -> dict:
        """retrieve entries by filter or ids.

        args:
            where: optional metadata filter.
            ids: optional list of specific ids to retrieve.

        returns:
            dict with ids, documents, and metadatas lists.
        """
        indices = list(range(len(self._entries)))

        if ids:
            id_set = set(ids)
            indices = [i for i in indices if self._entries[i]["id"] in id_set]

        if where:
            indices = self._apply_filter(indices, where)

        result_ids = []
        result_docs = []
        result_metas = []

        for idx in indices:
            entry = self._entries[idx]
            result_ids.append(entry["id"])
            result_docs.append(entry["document"])
            result_metas.append(entry["metadata"])

        return {
            "ids": result_ids,
            "documents": result_docs,
            "metadatas": result_metas,
        }

    def get_embeddings(self, where: Optional[dict] = None) -> dict:
        """retrieve stored vectors themselves, not just their documents.

        ``get`` deliberately omits embeddings because callers there want text.
        the graph builder needs the vectors to compute per-document centroids,
        and reading them back through ``query`` would be a similarity search
        against an arbitrary probe -- the wrong operation entirely.

        args:
            where: optional metadata filter, same semantics as ``get``.

        returns:
            dict with ids, embeddings (numpy array, shape (n, d)), and
            metadatas. embeddings is None when nothing matches.
        """
        indices = list(range(len(self._entries)))

        if where:
            indices = self._apply_filter(indices, where)

        if not indices:
            return {"ids": [], "embeddings": None, "metadatas": []}

        return {
            "ids": [self._entries[i]["id"] for i in indices],
            "embeddings": self._embeddings[indices],
            "metadatas": [self._entries[i]["metadata"] for i in indices],
        }

    def delete(self, ids: list[str]) -> int:
        """delete entries by their ids.

        args:
            ids: list of entry ids to remove.

        returns:
            number of entries deleted.
        """
        id_set = set(ids)
        original_count = len(self._entries)
        self._entries = [e for e in self._entries if e["id"] not in id_set]
        deleted = original_count - len(self._entries)

        if deleted > 0:
            self._rebuild_matrix()
            self._con.executemany(
                "DELETE FROM chunks WHERE id = ?", [(i,) for i in id_set]
            )
            self._con.commit()

        return deleted

    def count(self) -> int:
        """return the total number of entries in the store."""
        return len(self._entries)

    def _apply_filter(self, indices: list[int], where: dict) -> list[int]:
        """apply metadata filters to a list of indices.

        supports simple equality checks and the $in operator for
        matching against a list of values.

        args:
            indices: list of entry indices to filter.
            where: filter dictionary.

        returns:
            filtered list of indices.
        """
        result = []
        for idx in indices:
            meta = self._entries[idx]["metadata"]
            match = True
            for key, value in where.items():
                if isinstance(value, dict) and "$in" in value:
                    if meta.get(key) not in value["$in"]:
                        match = False
                        break
                else:
                    if meta.get(key) != value:
                        match = False
                        break
            if match:
                result.append(idx)
        return result


def get_vector_store() -> VectorStore:
    """return the singleton vector store instance.

    returns:
        the shared VectorStore instance.
    """
    global _store_instance
    if _store_instance is None:
        _store_instance = VectorStore()
    return _store_instance
