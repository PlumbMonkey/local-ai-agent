"""Retrieval-Augmented Generation (RAG) pipeline."""

import logging
from datetime import datetime
from typing import List, Optional

from core.memory.silos import CrossDomainQuery, DomainMemory

logger = logging.getLogger(__name__)


class AdvancedRAG:
    """Multi-stage retrieval pipeline with domain awareness."""

    def __init__(self):
        """Initialize RAG engine."""
        self.cross_domain_query = CrossDomainQuery()

    def query(
        self,
        question: str,
        domain: Optional[str] = None,
        top_k: int = 5,
        time_range: Optional[tuple] = None,
        expand_domains: bool = True,
    ) -> List[dict]:
        """
        Multi-stage retrieval pipeline.

        Args:
            question: User query
            domain: Filter to specific domain (optional)
            top_k: Number of results to return
            time_range: Optional (start_date, end_date) tuple
            expand_domains: Expand search if insufficient results

        Returns:
            List of relevant contexts with sources
        """
        logger.debug(f"RAG query: {question[:100]}... (domain: {domain})")

        # Stage 1: Domain-filtered or cross-domain search
        if domain:
            results = self._search_domain(question, domain, top_k)
        else:
            results = self._search_cross_domain(
                question,
                top_k=top_k,
                expand=expand_domains
            )

        # Stage 2: Time-based filtering (if specified)
        if time_range and results:
            results = self._filter_by_time(results, time_range)

        # Stage 3: Format results for context injection
        formatted = self._format_results(results, top_k)

        logger.info(f"Retrieved {len(formatted)} relevant contexts")
        return formatted

    def _search_domain(
        self,
        question: str,
        domain: str,
        top_k: int
    ) -> List[dict]:
        """Search single domain."""
        try:
            memory = DomainMemory(domain)
            return memory.query(question, top_k=top_k)
        except Exception as e:
            logger.error(f"Domain search failed: {e}")
            return []

    def _search_cross_domain(
        self,
        question: str,
        top_k: int,
        expand: bool
    ) -> List[dict]:
        """Search with cross-domain fallback."""
        if expand:
            return self.cross_domain_query.query(
                question,
                top_k=top_k,
                expand_to_other_domains=True
            )
        else:
            # Query all equally
            all_results = self.cross_domain_query.query_all_domains(
                question,
                top_k_per_domain=max(1, top_k // 5)
            )
            # Flatten to list
            flattened = []
            for domain_results in all_results.values():
                flattened.extend(domain_results)
            return flattened[:top_k]

    def _filter_by_time(
        self,
        results: List[dict],
        time_range: tuple
    ) -> List[dict]:
        """Filter results by timestamp."""
        if not time_range or len(time_range) != 2:
            return results

        start_date, end_date = time_range

        filtered = []
        for result in results:
            try:
                metadata = result.get("metadata", {})
                timestamp_str = metadata.get("timestamp", "")

                if timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    if start_date <= timestamp <= end_date:
                        filtered.append(result)
            except Exception as e:
                logger.warning(f"Time filtering failed for result: {e}")
                filtered.append(result)  # Include on error

        return filtered

    def _format_results(
        self,
        results: List[dict],
        top_k: int
    ) -> List[dict]:
        """Format results for LLM context injection."""
        formatted = []

        for i, result in enumerate(results[:top_k]):
            formatted.append({
                "rank": i + 1,
                "source": result.get("metadata", {}).get("domain", "unknown"),
                "content": result.get("document", ""),
                "relevance": 1.0 - (result.get("distance", 0) or 0),  # Convert distance to relevance
                "tags": result.get("metadata", {}).get("tags", "").split(","),
                "timestamp": result.get("metadata", {}).get("timestamp", ""),
            })

        return formatted

    def format_for_injection(self, results: List[dict]) -> str:
        """
        Format RAG results for prompt injection.

        Args:
            results: Formatted results from query()

        Returns:
            String to inject into prompt context
        """
        if not results:
            return ""

        context = "## Relevant Context from Memory:\n\n"

        for result in results:
            context += f"**[{result['source']}] #{result['rank']}**\n"
            context += f"Relevance: {result['relevance']:.0%}\n"
            context += f"Content: {result['content'][:500]}...\n"
            if result["tags"]:
                context += f"Tags: {', '.join(result['tags'][:3])}\n"
            context += "\n"

        return context
