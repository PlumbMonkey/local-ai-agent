"""
Ollama integration for local LLM inference.

Provides a simple client for querying local models via Ollama API.
"""

import logging
from typing import Optional

import requests

from core.config.settings import get_settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for Ollama local LLM API."""

    def __init__(self, endpoint: Optional[str] = None, timeout: Optional[int] = None):
        """
        Initialize Ollama client.

        Args:
            endpoint: Ollama API endpoint (default from settings)
            timeout: Request timeout in seconds (default from settings)
        """
        settings = get_settings()
        self.endpoint = endpoint or settings.ollama_endpoint
        self.timeout = timeout or settings.ollama_timeout

    def health_check(self) -> bool:
        """Check if Ollama service is running."""
        try:
            response = requests.get(f"{self.endpoint}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    def list_models(self) -> list[str]:
        """Get list of available models."""
        try:
            response = requests.get(f"{self.endpoint}/api/tags", timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list models: {e}")
            return []

    def generate(
        self,
        model: str,
        prompt: str,
        stream: bool = False,
        **kwargs,
    ) -> str:
        """
        Generate text using specified model.

        Args:
            model: Model name
            prompt: Input prompt
            stream: Stream response (not implemented for simple return)
            **kwargs: Additional parameters (temperature, top_k, etc.)

        Returns:
            Generated text
        """
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": stream,
                **kwargs,
            }

            response = requests.post(
                f"{self.endpoint}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

            if stream:
                # For streaming, accumulate all chunks
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        chunk = line.decode("utf-8")
                        if chunk.startswith("data: "):
                            chunk = chunk[6:]
                        try:
                            import json
                            data = json.loads(chunk)
                            full_response += data.get("response", "")
                        except Exception:
                            pass
                return full_response
            else:
                import json
                data = response.json()
                return data.get("response", "")

        except requests.exceptions.RequestException as e:
            logger.error(f"Generation failed: {e}")
            raise

    def embed(self, model: str, text: str) -> list[float]:
        """
        Generate embeddings for text.

        Args:
            model: Embedding model name
            text: Text to embed

        Returns:
            Embedding vector
        """
        try:
            payload = {
                "model": model,
                "prompt": text,
            }

            response = requests.post(
                f"{self.endpoint}/api/embeddings",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("embedding", [])

        except requests.exceptions.RequestException as e:
            logger.error(f"Embedding failed: {e}")
            raise

    def pull_model(self, model: str) -> bool:
        """
        Pull (download) a model.

        Args:
            model: Model name to pull

        Returns:
            True if successful
        """
        try:
            payload = {"name": model}

            response = requests.post(
                f"{self.endpoint}/api/pull",
                json=payload,
                timeout=None,  # Pull can take a long time
            )
            response.raise_for_status()
            logger.info(f"Successfully pulled model: {model}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to pull model: {e}")
            return False
