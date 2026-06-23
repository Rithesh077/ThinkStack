# thinkstack

offline slm-based research literature review agent and collaborative paper writer for independent researchers and students. packaged as a standalone desktop application.

## overview

thinkstack is a privacy-first, fully offline tool that helps researchers:
- ingest and index research papers (pdf)
- perform semantic and keyword search across their collection
- generate paper summaries and extract key claims
- identify research gaps and receive suggested directions
- **write academic papers** with an ai-assisted latex editor and real-time compiler
- **securely share** papers with authorized peers over a p2p network

all processing happens locally using `llama.cpp` (default) or `ollama` for language model inference and `sentence-transformers` for embeddings. no data leaves your machine. the application is bundled into a single executable using tauri.

## architecture

the system uses a tauri desktop shell orchestrating multiple sidecars and modules:

```text
src-tauri/              - rust backend (window management, ipc, p2p networking)
src/                    - react/vite frontend (ui, monaco editor, pdf viewer)
backend/                - python fastapi sidecar
  ├── domain/           - core business logic (analysis, ingestion, gap finder, latex generation)
  ├── api/              - rest endpoints
  └── infrastructure/   - local vector store, llm client wrappers
scripts/                - automated devops pipeline
```

## automated devops

every developer operation is automated to ensure a frictionless experience during development, production builds, and demonstrations.

### setup

a single command bootstraps the entire environment (installs system dependencies, rust, python venv, and node modules):

```bash
./scripts/setup.sh
```

### development

start the backend and frontend concurrently with hot-reloading:

```bash
./scripts/dev.sh
```

### validation

run pre-commit checks (syntax, imports, stale references) before pushing:

```bash
./scripts/validate.sh
```

### testing

run the comprehensive paper writer unit and integration test suite (validates file management, LaTeX compilation, log diagnostics, and the API endpoints over HTTP):

```bash
.venv/bin/python scripts/test_paper_writer.py
```

### production build

freeze the python backend using pyinstaller and compile the final tauri executable for your operating system:

```bash
./scripts/build.sh
```

## prerequisites (for manual setup)

if you are not using `./scripts/setup.sh`, ensure you have:
- python 3.11–3.13
- node.js 18 or higher
- rust toolchain (`rustup`)
- tauri system dependencies (`webkit2gtk`, `openssl`, `librsvg2`)
- a local gguf model file for llama.cpp

## technology stack

| component          | technology                              |
|--------------------|-----------------------------------------|
| desktop shell      | tauri (rust)                            |
| frontend           | react (vite) + typescript + vanilla css |
| backend            | python (fastapi) frozen via pyinstaller |
| slm runtime        | llama.cpp (gguf, cpu/ram optimized)     |
| embeddings         | sentence-transformers                   |
| vector store       | file-based numpy cosine store (json)    |
| pdf processing     | pymupdf + pdfplumber                    |
| latex compiler     | tectonic (rust-based, bundled sidecar)  |
| p2p networking     | libp2p (rust)                           |


## license

this project is for academic and research purposes.