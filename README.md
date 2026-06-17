# ThinkStack

offline slm-based research literature review agent for independent researchers and students.

## overview

 ThinkStack is a privacy-first, fully offline tool that helps researchers:
- ingest and index research papers (pdf)
- perform semantic and keyword search across their paper collection
- generate paper summaries and extract key claims
- identify research gaps and receive suggested research directions

all processing happens locally using llama.cpp (default) or ollama for language model inference
and sentence-transformers for embeddings. no data leaves your machine.

## architecture

the system uses a modular domain-driven architecture with six bounded contexts:

```
domain/ingestion/       - pdf parsing, text chunking, metadata extraction
domain/knowledge_base/  - chromadb storage, embedding generation
domain/search/          - semantic search, keyword search, hybrid ranking
domain/analysis/        - summarization, claim extraction, theme clustering
domain/gap_finder/      - gap analysis, research direction suggestions
api/                    - fastapi rest endpoints
frontend/               - react web interface
infrastructure/         - llm client, chromadb client, file management
```

## prerequisites

- python 3.11–3.13
- node.js 18 or higher
- a local gguf model file for llama.cpp (any instruction-tuned model, e.g.
  Gemma or Qwen). the file can live anywhere — you point the app at it with
  an environment variable (see step 3).
- optional: an NVIDIA GPU with recent drivers for faster inference
- optional: ollama installed and running instead of llama.cpp (https://ollama.com)

## setup

### 1. install python dependencies

a virtual environment is recommended so the install is identical on any
machine:

```bash
cd cs_mini_project
python -m venv .venv
# windows:        .venv\Scripts\activate
# macos / linux:  source .venv/bin/activate
pip install -r requirements.txt
```

> the first run downloads the sentence-transformers embedding model
> (`all-MiniLM-L6-v2`, ~90 MB) once and caches it locally; an internet
> connection is needed for that initial download only.

### 2. install and build the frontend

```bash
cd frontend
npm install
npm run build
```

### 3. point the app at your model (llama.cpp, the default)

the only machine-specific setting is the path to your gguf model file. set it
with an environment variable so the rest of the config works unchanged on any
device:

```bash
# windows (powershell):
$env:SCHOLARLENS_LLM_MODEL_PATH = "C:\path\to\model.gguf"
# macos / linux:
export SCHOLARLENS_LLM_MODEL_PATH="/path/to/model.gguf"
```

if `SCHOLARLENS_LLM_MODEL_PATH` points at a directory, the first `*.gguf`
file in it is used. you can drop two (or more) models in one directory and
switch between them at runtime from the model selector in the app sidebar
(see "switching models" below).

**prefer ollama instead of llama.cpp?**

```bash
export SCHOLARLENS_LLM_PROVIDER=ollama
export SCHOLARLENS_OLLAMA_MODEL=llama3.2
ollama pull llama3.2 && ollama serve
```

### 4. (optional) enable GPU acceleration

with an NVIDIA GPU you can run inference far faster. replace the CPU
llama-cpp build with the prebuilt CUDA wheel and its runtime libraries:

```bash
pip install llama-cpp-python --force-reinstall --no-cache-dir \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124
pip install nvidia-cuda-runtime-cu12 nvidia-cublas-cu12
```

then copy `cudart64_12.dll`, `cublas64_12.dll`, and `cublasLt64_12.dll` from
the installed `site-packages/nvidia/*/bin` folders into
`site-packages/llama_cpp/lib/`, and offload all layers to the GPU:

```bash
export SCHOLARLENS_LLM_GPU_LAYERS=-1   # -1 = all layers; 0 = cpu only
```

pick a model that fits your VRAM (a 4B Q4_K_M gguf needs ~3 GB).

### 5. start the application

```bash
python main.py
```

the application will be available at http://localhost:8000. the local model
loads lazily on the first request (a few seconds), then stays warm.

### switching models

if more than one `*.gguf` sits in your model directory, both appear in the
sidebar model selector. selecting one applies immediately if no model is
loaded yet; otherwise the choice is saved and applied on the next restart
(llama.cpp cannot swap a model in-process while one is resident on the gpu).
the selection is remembered in `data/active_model.txt`.

## development mode

for development with hot-reloading on both frontend and backend:

terminal 1 (backend):
```bash
python main.py
```

terminal 2 (frontend):
```bash
cd frontend
npm run dev
```

the frontend dev server runs on http://localhost:3000 and proxies
api requests to the backend on port 8000.

## api reference

| method | path                      | description                        |
|--------|---------------------------|------------------------------------|
| post   | /api/documents/upload     | upload a pdf research paper        |
| get    | /api/documents            | list all ingested papers           |
| get    | /api/documents/{id}       | get paper details                  |
| delete | /api/documents/{id}       | delete a paper                     |
| post   | /api/search               | hybrid semantic + keyword search   |
| post   | /api/analysis/summarize   | summarize selected papers          |
| post   | /api/analysis/claims      | extract claims from papers         |
| post   | /api/analysis/themes      | cluster papers by themes           |
| post   | /api/gaps/analyze         | run gap analysis                   |
| post   | /api/chat                 | rag chat assistant over your papers|
| get    | /api/system/health        | check system health                |
| get    | /api/system/models        | list available local llm models    |
| post   | /api/system/model         | switch the active llm model        |
| get    | /api/system/stats         | knowledge base statistics          |

## technology stack

| component       | technology                              |
|-----------------|-----------------------------------------|
| language        | python 3.11+                            |
| web framework   | fastapi + uvicorn                       |
| frontend        | react (vite)                            |
| slm runtime     | llama.cpp (gguf, cpu or cuda) or ollama |
| embeddings      | sentence-transformers (all-MiniLM-L6-v2)|
| vector store    | file-based numpy cosine store (json)    |
| pdf processing  | pymupdf + pdfplumber                    |
| keyword search  | rank-bm25                               |
| chat assistant  | retrieval-augmented (rag) over the store|

## configuration

all settings can be overridden via environment variables with the
`SCHOLARLENS_` prefix:

| variable                        | default            | description                |
|---------------------------------|--------------------|----------------------------|
| SCHOLARLENS_LLM_PROVIDER        | llama_cpp          | llm runtime: llama_cpp or ollama |
| SCHOLARLENS_LLM_MODEL_PATH      | _(set per machine)_ | path to a local .gguf file or a directory of them |
| SCHOLARLENS_LLM_CTX_SIZE        | 4096               | llama.cpp context window size |
| SCHOLARLENS_LLM_GPU_LAYERS      | -1                 | gpu layers to offload (-1=all, 0=cpu only) |
| SCHOLARLENS_OLLAMA_BASE_URL     | http://localhost:11434 | ollama api url          |
| SCHOLARLENS_OLLAMA_MODEL        | llama3.2           | target language model      |
| SCHOLARLENS_EMBEDDING_MODEL     | all-MiniLM-L6-v2   | sentence-transformer model |
| SCHOLARLENS_CHUNK_SIZE          | 512                | tokens per chunk           |
| SCHOLARLENS_CHUNK_OVERLAP       | 50                 | overlap between chunks     |
| SCHOLARLENS_SEARCH_TOP_K        | 10                 | default search results     |
| SCHOLARLENS_CHAT_MAX_TOKENS     | 512                | max tokens per chat reply  |
| SCHOLARLENS_CHAT_CONTEXT_CHUNKS | 5                  | chunks retrieved for chat context |
| SCHOLARLENS_PORT                | 8000               | server port                |

> note: the env-var prefix is `SCHOLARLENS_` (the app's internal name);
> only `SCHOLARLENS_LLM_MODEL_PATH` is machine-specific — everything else
> has a sensible default, so the same commands work on any device.

## project structure

```
cs_mini_project/
├── main.py                 # application entry point
├── config.py               # configuration module
├── requirements.txt        # python dependencies
├── domain/
│   ├── ingestion/          # pdf processing pipeline
│   ├── knowledge_base/     # vector storage and embeddings
│   ├── search/             # search and retrieval
│   ├── analysis/           # slm-powered analysis
│   └── gap_finder/         # research gap identification
├── infrastructure/         # external service adapters
├── api/                    # rest api routes
└── frontend/               # react web interface
```

## license

this project is for academic and research purposes.


## Futurr plan
1> Allow system to scan hardware and pick the best model.
2> Improve model slm using cloud
3> chroma db integration
4> 