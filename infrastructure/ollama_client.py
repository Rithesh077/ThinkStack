"""
llm client module.

provides a unified async client for local language model inference,
supporting both ollama and llama.cpp runtimes.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """async client for local llm runtimes (ollama or llama.cpp)."""

    def __init__(
        self,
        provider: str = settings.llm_provider,
        base_url: str = settings.ollama_base_url,
        model: str = settings.ollama_model,
        model_path: Path = settings.llm_model_path,
        ctx_size: int = settings.llm_ctx_size,
        gpu_layers: int = settings.llm_gpu_layers,
        timeout: int = settings.ollama_timeout,
    ):
        self.provider = provider.lower().strip()
        self.base_url = base_url
        self.model = model
        self.model_path = Path(model_path)
        self.ctx_size = ctx_size
        self.gpu_layers = gpu_layers
        self.timeout = timeout
        self._llama = None

    def _resolve_llama_model_path(self) -> Path:
        """resolve the configured llama.cpp model path.

        if a directory is provided, selects the first gguf file by name.
        """
        path = self.model_path
        if path.is_file():
            return path
        if path.is_dir():
            candidates = sorted(path.glob("*.gguf"))
            if candidates:
                return candidates[0]
        raise FileNotFoundError(f"llama.cpp model not found at {path}")

    def _get_llama(self):
        """lazily initialize llama.cpp model instance."""
        if self._llama is not None:
            return self._llama

        try:
            from llama_cpp import Llama
        except ImportError as e:
            raise RuntimeError(
                "llama-cpp-python is required for llm_provider=llama_cpp"
            ) from e

        model_path = self._resolve_llama_model_path()
        logger.info("loading llama.cpp model from %s", model_path)
        self._llama = Llama(
            model_path=str(model_path),
            n_ctx=self.ctx_size,
            n_gpu_layers=self.gpu_layers,
            verbose=False,
        )
        return self._llama

    async def _generate_ollama(
        self,
        prompt: str,
        system: Optional[str],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            return response.json().get("response", "")

    async def _generate_llama_cpp(
        self,
        prompt: str,
        system: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> str:
        llama = self._get_llama()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        result = await asyncio.to_thread(
            llama.create_chat_completion,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        choices = result.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return message.get("content", "")

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """generate text from the configured local llm runtime.

        args:
            prompt: the user prompt to send to the model.
            system: optional system prompt for context setting.
            temperature: sampling temperature, lower is more deterministic.
            max_tokens: maximum number of tokens in the response.

        returns:
            the generated text response from the model.

        supports:
            - ollama via /api/generate
            - llama.cpp via llama-cpp-python and a local gguf file
        """
        if self.provider == "llama_cpp":
            return await self._generate_llama_cpp(
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        return await self._generate_ollama(
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=False,
        )

    async def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """generate a response intended for json parsing.

        wraps the standard generate call with ollama's json format option
        to produce structured output suitable for parsing.

        args:
            prompt: the user prompt, should instruct json output.
            system: optional system prompt.
            temperature: sampling temperature.

        returns:
            raw json string from the model.
        """
        if self.provider == "llama_cpp":
            # llama.cpp does not guarantee strict json mode here;
            # downstream prompts already enforce valid json output.
            return await self._generate_llama_cpp(
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        return await self._generate_ollama(
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )

    async def list_models(self) -> list[dict]:
        """retrieve available model metadata for the active runtime.

        returns:
            list of model metadata dictionaries.
        """
        if self.provider == "llama_cpp":
            model_path = self._resolve_llama_model_path()
            return [{"name": model_path.name, "path": str(model_path)}]

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            return response.json().get("models", [])

    async def check_health(self) -> dict:
        """check whether configured llm runtime is available.

        returns:
            dictionary with status and available model information.
        """
        if self.provider == "llama_cpp":
            try:
                model_path = self._resolve_llama_model_path()
                try:
                    import llama_cpp  # noqa: F401
                    dependency_ok = True
                except ImportError:
                    dependency_ok = False

                return {
                    "status": "connected" if dependency_ok else "disconnected",
                    "provider": "llama_cpp",
                    "models_available": 1,
                    "target_model": model_path.name,
                    "target_available": True,
                    "model_list": [model_path.name],
                    "model_path": str(model_path),
                    "dependency_installed": dependency_ok,
                    "model_loaded": self._llama is not None,
                    "error": (
                        "llama-cpp-python is not installed"
                        if not dependency_ok
                        else ""
                    ),
                }
            except Exception as e:
                logger.warning("llama.cpp health check failed: %s", e)
                return {
                    "status": "disconnected",
                    "provider": "llama_cpp",
                    "error": str(e),
                    "target_model": str(self.model_path),
                }

        try:
            models = await self.list_models()
            model_names = [m.get("name", "") for m in models]
            has_target = any(self.model in name for name in model_names)
            return {
                "status": "connected",
                "provider": "ollama",
                "models_available": len(models),
                "target_model": self.model,
                "target_available": has_target,
                "model_list": model_names,
            }
        except (httpx.ConnectError, httpx.HTTPStatusError) as e:
            logger.warning("ollama health check failed: %s", e)
            return {
                "status": "disconnected",
                "provider": "ollama",
                "error": str(e),
                "target_model": self.model,
            }


ollama_client = OllamaClient()
