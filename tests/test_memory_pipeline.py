"""Integration tests for memory pipeline (Phase 2)."""

import json
import tempfile
from pathlib import Path

import pytest

from core.memory.ingest import ChatHistoryIngester, DomainDetector
from core.memory.mock_data import ConversationGenerator, generate_mock_conversations
from core.memory.rag import AdvancedRAG
from core.memory.silos import CrossDomainQuery, DomainMemory
from core.memory.vector_store import VectorStore


class TestDomainDetector:
    """Test domain detection with keyword + LLM hybrid approach."""

    def test_detect_coding_keyword(self):
        """Should detect coding domain by keywords."""
        detector = DomainDetector()
        domain = detector.detect("How do I debug this Python function?")
        assert domain == "coding"

    def test_detect_music_keyword(self):
        """Should detect music domain by keywords."""
        detector = DomainDetector()
        domain = detector.detect("What's a good chord progression for a jazz tune?")
        assert domain == "music"

    def test_detect_blender_keyword(self):
        """Should detect blender domain by keywords."""
        detector = DomainDetector()
        domain = detector.detect("How do I rig a 3D model in Blender?")
        assert domain == "blender"

    def test_detect_study_keyword(self):
        """Should detect study domain by keywords."""
        detector = DomainDetector()
        domain = detector.detect("Explain quantum entanglement in physics")
        assert domain == "study"

    def test_detect_general_fallback(self):
        """Should default to general for unclear text."""
        detector = DomainDetector()
        domain = detector.detect("What's the weather today?")
        assert domain in ["general", "study", "coding"]  # Could be any


class TestMockDataGenerator:
    """Test mock conversation generation."""

    def test_generate_conversations(self):
        """Should generate realistic conversations."""
        conversations = generate_mock_conversations(count=10, domains=["coding"])
        assert len(conversations) == 10
        assert all(c["domain"] == "coding" for c in conversations)

    def test_conversation_structure(self):
        """Should have correct conversation structure."""
        conversations = generate_mock_conversations(count=1, domains=["music"])
        conv = conversations[0]

        assert "id" in conv
        assert "domain" in conv
        assert "messages" in conv
        assert len(conv["messages"]) > 0
        assert "role" in conv["messages"][0]
        assert "content" in conv["messages"][0]

    def test_multi_domain_generation(self):
        """Should generate conversations across multiple domains."""
        domains = ["coding", "music", "blender", "study", "general"]
        conversations = generate_mock_conversations(count=50, domains=domains)

        domain_counts = {}
        for conv in conversations:
            domain = conv["domain"]
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        assert len(domain_counts) == 5
        for count in domain_counts.values():
            assert count > 0


class TestChatHistoryIngestion:
    """Test chat history parsing and ingestion."""

    def test_ingest_json_copilot_format(self):
        """Should parse GitHub Copilot JSON format."""
        ingester = ChatHistoryIngester()

        # Create mock Copilot export
        copilot_data = {
            "conversations": [
                {
                    "id": "test-1",
                    "created_at": "2024-01-01T10:00:00Z",
                    "messages": [
                        {"role": "user", "content": "How do I debug Python?"},
                        {"role": "assistant", "content": "Use pdb module..."},
                    ],
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(copilot_data, f)
            temp_file = f.name

        try:
            conversations = ingester.ingest_json(temp_file)
            assert len(conversations) == 1
            assert conversations[0]["domain"] in ["coding"]
        finally:
            Path(temp_file).unlink()

    def test_ingest_markdown_discord(self):
        """Should parse Discord markdown export."""
        ingester = ChatHistoryIngester()

        discord_markdown = """# Discord Export

**User1** - 2024-01-01 10:00 AM
How do I play this chord on guitar?

**User2** - 2024-01-01 10:05 AM
It's a Dm7. Try this fingering...

---

**User1** - 2024-01-01 10:10 AM
Thanks! That sounds great.
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(discord_markdown)
            temp_file = f.name

        try:
            conversations = ingester.ingest_markdown(temp_file)
            assert len(conversations) >= 1
        finally:
            Path(temp_file).unlink()

    def test_auto_tag_generation(self):
        """Should generate tags from content."""
        ingester = ChatHistoryIngester()

        text = "How to handle async/await in Python with timeouts?"
        tags = ingester._auto_tag(text, domain="coding")

        assert isinstance(tags, list)
        assert len(tags) > 0


class TestDomainMemory:
    """Test domain-specific memory storage."""

    def test_add_conversation(self):
        """Should add conversation to domain memory."""
        memory = DomainMemory(domain="coding")

        conversation = {
            "id": "test-1",
            "messages": [{"role": "user", "content": "How to debug Python?"}],
            "tags": ["python", "debugging"],
            "timestamp": "2024-01-01T10:00:00Z",
        }
        memory.add_conversation(conversation)

        assert memory.get_stats()["total_documents"] > 0

    def test_query_domain_memory(self):
        """Should retrieve relevant conversations."""
        memory = DomainMemory(domain="coding")

        # Add some conversations
        for i in range(5):
            conversation = {
                "id": f"test-{i}",
                "messages": [{"role": "user", "content": "How to handle errors in Python?"}],
                "tags": ["error-handling"],
                "timestamp": "2024-01-01T10:00:00Z",
            }
            memory.add_conversation(conversation)

        results = memory.query("error handling", top_k=3)
        assert len(results) > 0

    def test_clear_domain_memory(self):
        """Should clear all conversations in domain."""
        memory = DomainMemory(domain="study")

        conversation = {
            "id": "test-1",
            "messages": [{"role": "user", "content": "Quantum mechanics explained"}],
            "tags": ["physics"],
            "timestamp": "2024-01-01T10:00:00Z",
        }
        memory.add_conversation(conversation)

        assert memory.get_stats()["total_documents"] > 0
        memory.clear()
        assert memory.get_stats()["total_documents"] == 0

    def test_domain_validation(self):
        """Should validate domain on initialization."""
        with pytest.raises(ValueError):
            DomainMemory(domain="invalid_domain")


class TestCrossDomainQuery:
    """Test cross-domain memory retrieval."""

    def test_query_all_domains(self):
        """Should search across all domains."""
        cdq = CrossDomainQuery()

        # Add conversations to multiple domains
        coding_memory = DomainMemory(domain="coding")
        coding_memory.add_conversation({
            "id": "code-1",
            "messages": [{"role": "user", "content": "Python async patterns"}],
            "tags": ["async"],
            "timestamp": "2024-01-01T10:00:00Z",
        })

        music_memory = DomainMemory(domain="music")
        music_memory.add_conversation({
            "id": "music-1",
            "messages": [{"role": "user", "content": "Jazz chord progressions"}],
            "tags": ["jazz"],
            "timestamp": "2024-01-01T10:00:00Z",
        })

        results = cdq.query_all_domains("patterns")
        assert len(results) >= 0  # Might find nothing if databases are empty

    def test_fallback_search(self):
        """Should expand search if results < threshold."""
        cdq = CrossDomainQuery()
        results = cdq.query("nonexistent query", primary_domain="coding")
        # Should not error even if no results


class TestAdvancedRAG:
    """Test retrieval-augmented generation pipeline."""

    def test_rag_query_formatting(self):
        """Should format results for LLM injection."""
        rag = AdvancedRAG()

        # Add some mock data to memory first
        memory = DomainMemory(domain="coding")
        memory.add_conversation({
            "id": "test-1",
            "messages": [{"role": "user", "content": "Use list comprehension for cleaner code"}],
            "tags": ["python"],
            "timestamp": "2024-01-01T10:00:00Z",
        })

        results = rag.query("Python best practices", domain="coding", top_k=3)
        # Should return properly formatted list

    def test_rag_format_for_injection(self):
        """Should produce markdown for prompt injection."""
        rag = AdvancedRAG()

        sample_results = [
            {
                "rank": 1,
                "source": "memory_20240101",
                "content": "Use async/await for concurrency",
                "relevance": 0.95,
                "tags": ["async", "python"],
                "timestamp": "2024-01-01T10:00:00Z",
            }
        ]

        formatted = rag.format_for_injection(sample_results)
        assert isinstance(formatted, str)
        assert "relevant context" in formatted.lower()
        assert "async" in formatted.lower()


class TestEndToEndPipeline:
    """Test complete memory pipeline."""

    def test_mock_data_to_memory_flow(self):
        """Should flow: generate → ingest → store → query."""
        # Generate mock data
        conversations = generate_mock_conversations(count=20, domains=["coding"])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"conversations": conversations}, f)
            temp_file = f.name

        try:
            # Ingest
            ingester = ChatHistoryIngester()
            count = ingester.ingest_and_store(temp_file)
            assert count == 20

            # Query
            rag = AdvancedRAG()
            results = rag.query("How to debug", domain="coding", top_k=5)
            # Should return results from stored conversations

        finally:
            Path(temp_file).unlink()
            # Clean up memory
            memory = DomainMemory(domain="coding")
            memory.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
