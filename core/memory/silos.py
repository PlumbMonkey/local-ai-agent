"""Domain-specific memory silos with ChromaDB."""

import logging
from typing import List, Optional

from core.config.settings import get_settings
from core.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)


class DomainMemory:
    """Manage domain-specific knowledge base."""

    # Valid domains
    VALID_DOMAINS = ["coding", "music", "blender", "study", "general"]

    def __init__(self, domain: str):
        """
        Initialize domain memory.

        Args:
            domain: Domain name (coding, music, blender, study, general)

        Raises:
            ValueError: If invalid domain
        """
        if domain not in self.VALID_DOMAINS:
            raise ValueError(f"Invalid domain: {domain}. Must be one of {self.VALID_DOMAINS}")

        self.domain = domain
        self.collection_name = f"{domain}_memory"
        self.vector_store = VectorStore(collection_name=self.collection_name)

    def add_conversation(self, conversation: dict) -> None:
        """
        Add conversation to domain memory.

        Args:
            conversation: Normalized conversation dict with embedding
        """
        # Extract content for storage
        conv_id = conversation.get("id", "")
        messages = conversation.get("messages", [])
        timestamp = conversation.get("timestamp", "")
        tags = conversation.get("tags", [])

        # Combine all text for semantic search
        text_content = " ".join(
            msg.get("content", "") for msg in messages
        )

        if not text_content.strip():
            logger.warning("Skipping conversation with no text content")
            return

        metadata = {
            "domain": self.domain,
            "timestamp": timestamp,
            "tags": ",".join(tags),
            "message_count": len(messages),
        }

        # Store in vector store
        self.vector_store.add_documents(
            documents=[text_content],
            metadatas=[metadata],
            ids=[conv_id] if conv_id else None,
        )

        logger.debug(f"Added conversation to {self.domain}_memory")

    def query(
        self,
        question: str,
        top_k: int = 5,
        time_range: Optional[tuple] = None,
    ) -> List[dict]:
        """
        Query domain-specific memory.

        Args:
            question: Query text
            top_k: Number of results to return
            time_range: Optional (start_date, end_date) filter

        Returns:
            List of relevant conversations with metadata
        """
        results = self.vector_store.query(question, n_results=top_k)

        # TODO: Add time-based filtering when needed
        # if time_range:
        #     start, end = time_range
        #     results = [r for r in results if start <= r["metadata"]["timestamp"] <= end]

        return results

    def clear(self) -> None:
        """Clear all data in this domain."""
        self.vector_store.clear()
        logger.info(f"Cleared {self.domain}_memory")

    def get_stats(self) -> dict:
        """Get statistics about this domain's memory."""
        # TODO: Implement with ChromaDB collection stats
        return {
            "domain": self.domain,
            "collection": self.collection_name,
        }


class CrossDomainQuery:
    """Query across multiple domains with fallback."""

    def __init__(self):
        """Initialize cross-domain query engine."""
        self.domains = DomainMemory.VALID_DOMAINS
        self.memories = {domain: DomainMemory(domain) for domain in self.domains}

    def query(
        self,
        question: str,
        primary_domain: Optional[str] = None,
        top_k: int = 5,
        expand_to_other_domains: bool = True,
    ) -> List[dict]:
        """
        Query with domain fallback.

        Args:
            question: Query text
            primary_domain: Domain to search first (optional)
            top_k: Total results to return
            expand_to_other_domains: If primary returns <3, search others

        Returns:
            List of relevant results across domains
        """
        all_results = []

        # Step 1: Search primary domain if specified
        if primary_domain and primary_domain in self.memories:
            primary_results = self.memories[primary_domain].query(question, top_k=top_k)
            all_results.extend(primary_results)

            # If we have enough results, return
            if len(all_results) >= 3:
                return all_results[:top_k]

        # Step 2: Expand to other domains if insufficient results
        if expand_to_other_domains:
            remaining_needed = top_k - len(all_results)

            for domain in self.domains:
                if primary_domain and domain == primary_domain:
                    continue  # Already searched

                other_results = self.memories[domain].query(
                    question,
                    top_k=max(1, remaining_needed // (len(self.domains) - 1))
                )
                all_results.extend(other_results)

        return all_results[:top_k]

    def query_all_domains(
        self,
        question: str,
        top_k_per_domain: int = 3,
    ) -> dict:
        """
        Query all domains separately and return organized results.

        Args:
            question: Query text
            top_k_per_domain: Results per domain

        Returns:
            Dict with results organized by domain
        """
        results = {}

        for domain in self.domains:
            results[domain] = self.memories[domain].query(question, top_k=top_k_per_domain)

        return results

    def clear_all(self) -> None:
        """Clear all domain memories."""
        for domain in self.domains:
            self.memories[domain].clear()
        logger.info("Cleared all domain memories")
