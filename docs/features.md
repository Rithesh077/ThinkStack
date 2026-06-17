# Current Features and Known Issues

## Current Features

1. **Document Ingestion Pipeline**
   - Cascading PDF parser: Tries PyMuPDF (fast) first, falls back to `pdfplumber` for scanned or complex layouts.
   - Text chunking algorithm with overlap and page-number retention using word-overlap scoring.
   - Metadata extraction via RegEx with SLM (Small Language Model) fallback.

2. **Offline Knowledge Base**
   - Custom NumPy-based local vector store (zero external DB dependencies).
   - Local embeddings using `sentence-transformers` (`all-MiniLM-L6-v2`).

3. **Hybrid Search**
   - Semantic Search (Cosine similarity via embeddings).
   - Keyword Search (BM25 token matching).
   - Reciprocal Rank Fusion (RRF) to merge and rank results.

4. **Analysis & Gap Finder**
   - Single and multi-paper comparative summarization.
   - Thematic clustering.
   - Gap analysis (contradictions, methodological, missing validation, etc.) and actionable research suggestions.
   - Single, efficient LLM calls for gap orchestration.

5. **Local LLM Integration**
   - Dual-runtime client: Supports both **Ollama** (API) and **llama.cpp** (direct memory loading via GGUF).
   - GBNF grammar constraints for strict JSON output when using `llama_cpp`.
   - GPU-acceleration fallback logic (tries GPU, falls back to CPU on OOM).

## Known Issues

1. **BM25 Search Performance**: The BM25 index is built from scratch on every keyword search query. This is acceptable for a small corpus but will become a bottleneck as the document count grows.
2. **Analysis Route Duplication**: `routes_gaps.py` partially duplicates summarization logic found in `summarizer.py`. (Intentional for efficiency, but adds maintenance overhead).
3. **LLM Retry Logic**: While GBNF handles `llama_cpp`, there's no extensive retry logic if Ollama hallucinates malformed JSON.
