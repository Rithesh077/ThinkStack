"""
scholarlens configuration module.

centralizes all application settings including paths, model names,
chunking parameters, and server configuration. uses pydantic-settings
for environment variable overrides.
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """application-wide configuration with sensible defaults for offline use."""

    # paths
    base_dir: Path = Path(__file__).parent
    data_dir: Path = Path(__file__).parent / "data"
    papers_dir: Path = Path(__file__).parent / "data" / "papers"
    chroma_dir: Path = Path(__file__).parent / "data" / "vectorstore"

    # llm runtime
    llm_provider: str = "llama_cpp"
    llm_model_path: Path = Path(r"E:\odysseus\data\models\Qwen3-4B-Instruct-2507-Q4_K_M.gguf")
    llm_ctx_size: int = 4096
    llm_gpu_layers: int = 0

    # ollama (optional fallback runtime)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout: int = 120

    # embeddings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # chunking
    chunk_size: int = 512
    chunk_overlap: int = 50

    # search
    search_top_k: int = 10
    similarity_threshold: float = 0.3

    # server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True



    model_config = {"env_prefix": "SCHOLARLENS_"}


settings = Settings()
