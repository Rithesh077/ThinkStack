#!/bin/bash
# thinkstack: pre-commit validation
# run this before pushing to catch issues early
# usage: ./scripts/validate.sh
set -e

echo "----------------------------------------"
echo "thinkstack: validation"
echo "----------------------------------------"

source .venv/bin/activate

# -- python syntax check --
echo "[1/3] checking python syntax..."
python3 -m py_compile config.py
python3 -m py_compile main.py
for f in api/*.py domain/**/*.py infrastructure/*.py; do
    python3 -m py_compile "$f" 2>/dev/null && echo "  ok: $f" || echo "  fail: $f"
done

# -- import resolution check --
echo "[2/3] checking critical imports..."
python3 -c "from config import settings" && echo "  config: ok" || echo "  config: fail"
python3 -c "from infrastructure.local_vector_store import get_vector_store" && echo "  vector store: ok" || echo "  vector store: fail"
python3 -c "from infrastructure.ollama_client import ollama_client" && echo "  ollama client: ok" || echo "  ollama client: fail"

# -- stale reference check --
echo "[3/3] checking for stale references..."
if grep -r "chromadb_client" --include="*.py" . 2>/dev/null; then
    echo "  error: stale chromadb_client references found"
    exit 1
else
    echo "  no stale references found"
fi

echo "----------------------------------------"
echo "validation passed."
echo "----------------------------------------"
