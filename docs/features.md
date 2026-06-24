# current features and known issues

## current features

1. **desktop architecture & devops**
   - standalone cross-platform executable via tauri (rust).
   - python fastapi sidecar seamlessly bundled using pyinstaller.
   - one-click automated devops pipeline for setup, development, validation, and building.

2. **document ingestion pipeline**
   - cascading pdf parser: tries pymupdf (fast) first, falls back to `pdfplumber` for scanned or complex layouts.
   - text chunking algorithm with overlap and page-number retention using word-overlap scoring.
   - metadata extraction via regex with slm (small language model) fallback.

3. **offline knowledge base**
   - custom numpy-based local vector store (zero external db dependencies).
   - local embeddings using `sentence-transformers` (`all-minilm-l6-v2`).

4. **hybrid search**
   - semantic search (cosine similarity via embeddings).
   - keyword search (bm25 token matching).
   - reciprocal rank fusion (rrf) to merge and rank results.

5. **analysis & gap finder**
   - single and multi-paper comparative summarization.
   - thematic clustering.
   - gap analysis (contradictions, methodological, missing validation) and actionable research suggestions.

6. **local llm integration**
   - dual-runtime client: supports both ollama and llama.cpp (direct memory loading via gguf).
   - gbnf grammar constraints for strict json and latex output when using llama_cpp.
   - gpu-acceleration fallback logic (tries gpu, falls back to cpu on oom).

7. **document encryption**
   - per-paper encryption at rest using aes-256-gcm with an argon2id key-derivation function.
   - encrypt / decrypt-and-view / remove-encryption flows exposed via `/api/encryption`.

8. **ai-assisted latex paper writer**
   - file-based project workspace (`data/papers_workspace/<project_id>/`) with create / save / list / delete and a starter academic template.
   - `/api/papers/generate` turns a plain-language or pseudo-code prompt into raw, compilable latex body content using the local slm (no `\documentclass`/`\begin{document}` wrapper, no markdown fences).
   - offline pdf compilation via `pdflatex` (run twice for cross-references, non-interactive, 60s timeout) with meaningful error extraction from the `.log`; compiled pdf served from `/api/papers/download/{project_id}`.
   - editor surfaced in the tauri desktop frontend (`src/components/PaperWriter.tsx`).

## known issues

1. **bm25 search performance**: the bm25 index is built from scratch on every keyword search query. this is acceptable for a small corpus but will become a bottleneck as the document count grows.
2. **analysis route duplication**: `routes_gaps.py` partially duplicates summarization logic found in `summarizer.py`. (intentional for efficiency, but adds maintenance overhead).
3. **llm retry logic**: while gbnf handles `llama_cpp`, there's no extensive retry logic if ollama hallucinates malformed structures.
4. **latex compiler dependency**: the paper writer currently shells out to a system `pdflatex` (a full tex installation must be on `PATH`), rather than the planned bundled `tectonic` sidecar. compilation fails gracefully with a 422 if `pdflatex` is missing.
