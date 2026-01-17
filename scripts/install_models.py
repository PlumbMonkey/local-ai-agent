"""Setup script for installing Ollama models."""

import logging
from pathlib import Path

from core.llm.ollama import OllamaClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RECOMMENDED_MODELS = [
    "qwen2.5-coder:7b",
    "deepseek-r1:8b",
    "nomic-embed-text",
]


def main():
    """Download recommended models."""
    client = OllamaClient()

    if not client.health_check():
        logger.error("Ollama not running. Please start Ollama first.")
        return 1

    logger.info("Pulling recommended models...")

    for model in RECOMMENDED_MODELS:
        logger.info(f"Pulling {model}...")
        success = client.pull_model(model)
        if success:
            logger.info(f"✅ {model}")
        else:
            logger.error(f"❌ {model}")

    logger.info("Done!")
    return 0


if __name__ == "__main__":
    exit(main())
