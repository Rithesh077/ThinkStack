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

- python 3.11 or higher
- node.js 18 or higher
- local gguf model file for llama.cpp (default)
- optional: ollama installed and running (https://ollama.com)

## setup

### 1. install python dependencies

```bash
cd cs_mini_project
pip install -r requirements.txt
```

### 2. install and build the frontend

```bash
cd frontend
npm install
npm run build
```

### 3. configure local model runtime (default: llama.cpp)

by default, the app is configured to use:

- model path: `E:\odysseus\data\models\Qwen3-4B-Instruct-2507-Q4_K_M.gguf`
- provider: `llama_cpp`

if you prefer ollama instead, set:

```bash
set SCHOLARLENS_LLM_PROVIDER=ollama
set SCHOLARLENS_OLLAMA_MODEL=llama3.2
```

then run ollama:

```bash
ollama pull llama3.2
ollama serve
```

### 4. start the application

```bash
python main.py
```

the application will be available at http://localhost:8000.

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
| get    | /api/system/health        | check system health                |
| get    | /api/system/models        | list available local llm models    |
| get    | /api/system/stats         | knowledge base statistics          |

## technology stack

| component       | technology                              |
|-----------------|-----------------------------------------|
| language        | python 3.11+                            |
| web framework   | fastapi + uvicorn                       |
| frontend        | react (vite)                            |
| slm runtime     | llama.cpp (gguf) or ollama              |
| embeddings      | sentence-transformers (all-MiniLM-L6-v2)|
| vector database | chromadb (persistent, file-based)       |
| pdf processing  | pymupdf + pdfplumber                    |
| keyword search  | rank-bm25                               |

## configuration

all settings can be overridden via environment variables with the
`SCHOLARLENS_` prefix:

| variable                        | default            | description                |
|---------------------------------|--------------------|----------------------------|
| SCHOLARLENS_LLM_PROVIDER        | llama_cpp          | llm runtime: llama_cpp or ollama |
| SCHOLARLENS_LLM_MODEL_PATH      | E:\odysseus\data\models\Qwen3-4B-Instruct-2507-Q4_K_M.gguf | gguf model path |
| SCHOLARLENS_LLM_CTX_SIZE        | 4096               | llama.cpp context window size |
| SCHOLARLENS_LLM_GPU_LAYERS      | 0                  | llama.cpp gpu layers (0=cpu) |
| SCHOLARLENS_OLLAMA_BASE_URL     | http://localhost:11434 | ollama api url          |
| SCHOLARLENS_OLLAMA_MODEL        | llama3.2           | target language model      |
| SCHOLARLENS_EMBEDDING_MODEL     | all-MiniLM-L6-v2   | sentence-transformer model |
| SCHOLARLENS_CHUNK_SIZE          | 512                | tokens per chunk           |
| SCHOLARLENS_CHUNK_OVERLAP       | 50                 | overlap between chunks     |
| SCHOLARLENS_SEARCH_TOP_K        | 10                 | default search results     |
| SCHOLARLENS_PORT                | 8000               | server port                |

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
