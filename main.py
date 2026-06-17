"""
scholarlens application entry point.

configures and starts the fastapi server with all api routers,
static file serving for the react frontend, cors middleware,
and startup/shutdown lifecycle events.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from infrastructure.file_manager import ensure_directories
from infrastructure.chromadb_client import get_vector_store
from api.routes_documents import router as documents_router
from api.routes_search import router as search_router
from api.routes_analysis import router as analysis_router
from api.routes_gaps import router as gaps_router
from api.routes_system import router as system_router
from api.routes_chat import router as chat_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scholarlens")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """handle startup and shutdown tasks."""
    logger.info("initializing scholarlens")
    ensure_directories()
    get_vector_store()
    logger.info("scholarlens ready at http://%s:%s", settings.host, settings.port)
    yield
    logger.info("shutting down scholarlens")


app = FastAPI(
    title="scholarlens",
    description="offline slm-based research literature review agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router, prefix="/api/documents", tags=["documents"])
app.include_router(search_router, prefix="/api/search", tags=["search"])
app.include_router(analysis_router, prefix="/api/analysis", tags=["analysis"])
app.include_router(gaps_router, prefix="/api/gaps", tags=["gaps"])
app.include_router(system_router, prefix="/api/system", tags=["system"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])

frontend_dist = settings.base_dir / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
