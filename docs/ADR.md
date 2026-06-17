# Architecture Decision Records (ADR)

## 2026-06-16: Project Renaming
**Decision:** Renamed the project from `ScholarLens` to `Think Stack`.
**Rationale:** The project scope has evolved into a broader, edge-AI focused research assistant.
**Status:** Accepted.

## 2026-06-17: Backend Infrastructure Audit & Fixes
**Decision 1:** Renamed `chromadb_client.py` to `local_vector_store.py`.
**Rationale:** The module did not use ChromaDB. It was a custom NumPy-based cosine similarity implementation. The new name accurately reflects its function.

**Decision 2:** Added GBNF Grammar to `llama_cpp` client.
**Rationale:** Prevented the LLM from outputting conversational filler before JSON (e.g., "Here is your JSON:"). This strict enforcement stops `json.loads()` crashes in downstream analysis modules.

**Decision 3:** Added GPU Fallback.
**Rationale:** On machines where VRAM is insufficient (OOM errors), the model will gracefully fallback to CPU-only inference rather than crashing the application.

---
