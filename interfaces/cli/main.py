"""Command-line interface for Local AI Agent."""

import logging
import sys

from core.config.settings import get_settings
from core.llm.ollama import OllamaClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Main CLI entry point."""
    settings = get_settings()
    client = OllamaClient()

    print("🤖 Local AI Agent CLI")
    print(f"Endpoint: {client.endpoint}")

    # Check health
    if not client.health_check():
        print("❌ Ollama service not running!")
        print(f"Start Ollama: {client.endpoint}")
        sys.exit(1)

    print("✅ Ollama connected")

    # List models
    models = client.list_models()
    if not models:
        print("❌ No models available")
        print("Pull a model: ollama pull qwen2.5-coder:7b")
        sys.exit(1)

    print(f"📦 Available models: {', '.join(models)}")

    # Interactive chat
    print("\n💬 Chat mode (type 'exit' to quit)\n")

    while True:
        try:
            prompt = input("You: ").strip()
            if prompt.lower() in ("exit", "quit"):
                print("Goodbye! 👋")
                break

            if not prompt:
                continue

            print(f"\n🤖 {settings.model_primary}:")
            response = client.generate(
                model=settings.model_primary,
                prompt=prompt,
                temperature=0.7,
            )
            print(response)
            print()

        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"❌ Error: {e}\n")


if __name__ == "__main__":
    main()
