#!/bin/bash
# thinkstack: production build pipeline
# freezes the python backend and compiles the tauri desktop binary
# usage: ./scripts/build.sh
set -e

echo "----------------------------------------"
echo "thinkstack: production build"
echo "----------------------------------------"

# -- detect target triple --
ARCH=$(uname -m)
OS=$(uname -s)
case "$OS" in
    Linux)  TRIPLE="${ARCH}-unknown-linux-gnu" ;;
    Darwin) TRIPLE="${ARCH}-apple-darwin" ;;
    *)      TRIPLE="${ARCH}-pc-windows-msvc" ;;
esac
echo "target triple: ${TRIPLE}"

# -- freeze python backend --
echo "[1/3] freezing python backend with pyinstaller..."
source .venv/bin/activate
pyinstaller --name thinkstack-api --onefile --clean \
    --hidden-import uvicorn \
    --hidden-import uvicorn.logging \
    --hidden-import uvicorn.loops \
    --hidden-import uvicorn.loops.auto \
    --hidden-import uvicorn.protocols \
    --hidden-import uvicorn.protocols.http \
    --hidden-import uvicorn.protocols.http.auto \
    --hidden-import uvicorn.protocols.websockets \
    --hidden-import uvicorn.protocols.websockets.auto \
    --hidden-import uvicorn.lifespan \
    --hidden-import uvicorn.lifespan.on \
    main.py
echo "  backend frozen to dist/thinkstack-api"

# -- prepare tauri sidecar directory --
echo "[2/3] preparing sidecar directory..."
mkdir -p src-tauri/bin
cp dist/thinkstack-api "src-tauri/bin/thinkstack-api-${TRIPLE}"
echo "  sidecar placed at src-tauri/bin/thinkstack-api-${TRIPLE}"

# -- compile tauri desktop app --
echo "[3/3] compiling tauri desktop application..."
if [ -d "src-tauri" ] && [ -f "src-tauri/tauri.conf.json" ]; then
    npm run tauri build
    echo "  desktop binary compiled"
else
    echo "  tauri not scaffolded. skipping final compilation."
    echo "  frozen backend available at: src-tauri/bin/thinkstack-api-${TRIPLE}"
fi

echo "----------------------------------------"
echo "build complete."
echo "----------------------------------------"
