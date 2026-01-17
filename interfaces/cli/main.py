"""Command-line interface for Local AI Agent."""

import logging
import sys
from pathlib import Path

from core.config.settings import get_settings
from core.llm.ollama import OllamaClient
from core.memory.ingest import ChatHistoryIngester
from core.memory.mock_data import generate_mock_conversations, save_mock_data_as_json
from core.memory.rag import AdvancedRAG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def cmd_chat():
    """Interactive chat mode."""
    settings = get_settings()
    client = OllamaClient()

    print("🤖 Local AI Agent CLI")
    print(f"Endpoint: {client.endpoint}")

    # Check health
    if not client.health_check():
        print("❌ Ollama service not running!")
        print(f"Start Ollama: {client.endpoint}")
        return 1

    print("✅ Ollama connected")

    # List models
    models = client.list_models()
    if not models:
        print("❌ No models available")
        print("Pull a model: ollama pull qwen2.5-coder:7b")
        return 1

    print(f"📦 Available models: {', '.join(models)}")

    # Interactive chat
    print("\n💬 Chat mode (type 'exit' to quit)\n")

    rag = AdvancedRAG()

    while True:
        try:
            prompt = input("You: ").strip()
            if prompt.lower() in ("exit", "quit"):
                print("Goodbye! 👋")
                break

            if not prompt:
                continue

            # Try to retrieve context from memory
            try:
                context_results = rag.query(prompt, top_k=3)
                if context_results:
                    print("\n📚 Using context from memory...")
            except Exception as e:
                logger.debug(f"Memory lookup failed: {e}")
                context_results = []

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

    return 0


def cmd_import_history(filepath: str):
    """Import chat history from file."""
    print(f"📥 Importing chat history from: {filepath}")

    ingester = ChatHistoryIngester()

    try:
        count = ingester.ingest_and_store(filepath)
        print(f"✅ Successfully imported {count} conversations")
        return 0
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return 1


def cmd_generate_mock_data(count: int = 1000):
    """Generate mock chat data for testing."""
    filepath = "examples/mock_chat_export.json"
    print(f"🔄 Generating {count} mock conversations...")

    save_mock_data_as_json(filepath, count)
    return 0


def cmd_query_memory(question: str):
    """Query memory for relevant context."""
    print(f"🔍 Searching memory for: {question}\n")

    rag = AdvancedRAG()

    try:
        results = rag.query(question, top_k=5)

        if not results:
            print("No relevant context found in memory.")
            return 0

        for i, result in enumerate(results, 1):
            print(f"\n[{i}] {result['source'].upper()}")
            print(f"    Relevance: {result['relevance']:.0%}")
            print(f"    Content: {result['content'][:200]}...")
            if result["tags"]:
                print(f"    Tags: {', '.join(result['tags'])}")

        return 0

    except Exception as e:
        print(f"❌ Query failed: {e}")
        return 1


def print_help():
    """Print help message."""
    print("""
🤖 Local AI Agent - Commands:

  chat                          Interactive chat mode (default)
  import-history <file>         Import chat history (JSON/MD)
  generate-mock-data [count]    Generate test data (default: 1000)
  query-memory <question>       Search memory for context
  help                          Show this help message

Examples:
  python -m interfaces.cli.main chat
  python -m interfaces.cli.main import-history exports/copilot.json
  python -m interfaces.cli.main query-memory "How did I handle async timeouts?"
  python -m interfaces.cli.main generate-mock-data 500
    """)


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        return cmd_chat()

    command = sys.argv[1].lower()

    if command == "chat":
        return cmd_chat()
    elif command == "import-history":
        if len(sys.argv) < 3:
            print("❌ Usage: import-history <file>")
            return 1
        return cmd_import_history(sys.argv[2])
    elif command == "generate-mock-data":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
        return cmd_generate_mock_data(count)
    elif command == "query-memory":
        if len(sys.argv) < 3:
            print("❌ Usage: query-memory <question>")
            return 1
        question = " ".join(sys.argv[2:])
        return cmd_query_memory(question)
    elif command in ("help", "--help", "-h"):
        print_help()
        return 0
    else:
        print(f"❌ Unknown command: {command}")
        print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
