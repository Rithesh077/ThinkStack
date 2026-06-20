"""
ollama client module.

provides an async http client for communicating with the ollama api.
handles text generation, model listing, and health checks.
all communication happens over localhost for offline operation.
"""

import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """async client for the ollama local llm api."""

    def __init__(
        self,
        base_url: str = settings.ollama_base_url,
        model: str = settings.ollama_model,
        timeout: int = settings.ollama_timeout,
    ):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """send a generation request to ollama and return the full response text.

        args:
            prompt: the user prompt to send to the model.
            system: optional system prompt for context setting.
            temperature: sampling temperature, lower is more deterministic.
            max_tokens: maximum number of tokens in the response.

        returns:
            the generated text response from the model.

        raises:
            httpx.ConnectError: if ollama is not running.
            httpx.HTTPStatusError: if ollama returns an error status.
        """
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

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            return response.json().get("response", "")

    async def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
    ) -> str:
        """generate a response with json format enforcement.

        wraps the standard generate call with ollama's json format option
        to produce structured output suitable for parsing.

        args:
            prompt: the user prompt, should instruct json output.
            system: optional system prompt.
            temperature: sampling temperature.

        returns:
            raw json string from the model.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": temperature,
                "num_predict": 4096,
            },
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            return response.json().get("response", "")

    async def list_models(self) -> list[dict]:
        """retrieve the list of models available in the local ollama instance.

        returns:
            list of model metadata dictionaries.
        """
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            return response.json().get("models", [])

    async def check_health(self) -> dict:
        """check whether ollama is running and reachable.

        returns:
            dictionary with status and available model information.
        """
        try:
            models = await self.list_models()
            model_names = [m.get("name", "") for m in models]
            has_target = any(self.model in name for name in model_names)
            return {
                "status": "connected",
                "models_available": len(models),
                "target_model": self.model,
                "target_available": has_target,
                "model_list": model_names,
            }
        except (httpx.ConnectError, httpx.HTTPStatusError) as e:
            logger.warning("ollama health check failed: %s", e)
            return {
                "status": "disconnected",
                "error": str(e),
                "target_model": self.model,
            }


ollama_client = OllamaClient()
