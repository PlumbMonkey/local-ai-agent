"""Chat history ingestion pipeline with multi-format support."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from core.config.settings import get_settings
from core.llm.ollama import OllamaClient
from core.memory.silos import DomainMemory

logger = logging.getLogger(__name__)


class DomainDetector:
    """Detect conversation domain using hybrid approach."""

    # Keywords for fast matching (99% of cases)
    DOMAIN_KEYWORDS = {
        "coding": [
            "python", "javascript", "java", "c++", "function", "class", "import",
            "debug", "error", "exception", "algorithm", "loop", "variable",
            "database", "sql", "api", "rest", "graphql", "typescript", "react"
        ],
        "music": [
            "chord", "midi", "mix", "bpm", "daw", "ableton", "reaper", "logic",
            "eq", "reverb", "compression", "sidechain", "kick", "bass", "drum",
            "synth", "vst", "audio", "wave", "frequency", "hz", "melody", "harmony"
        ],
        "blender": [
            "blender", "material", "render", "node", "mesh", "uv", "armature",
            "rigging", "animation", "bake", "shader", "principled", "geometry",
            "modeling", "sculpting", "texture"
        ],
        "study": [
            "paper", "research", "study", "quiz", "notes", "learning", "exam",
            "textbook", "chapter", "theorem", "equation", "formula", "academic",
            "thesis", "journal", "reference"
        ]
    }

    def __init__(self):
        """Initialize detector with settings."""
        self.settings = get_settings()
        self.llm_client = OllamaClient()
        self.keyword_scores = {}

    def detect(self, text: str) -> str:
        """
        Detect domain using hybrid approach.

        1. Fast keyword matching (99% of cases, <1ms)
        2. LLM classification for ambiguous cases (1%, ~1s)

        Args:
            text: Conversation text

        Returns:
            Domain name (coding, music, blender, study, or general)
        """
        # Step 1: Keyword matching
        scores = {}
        text_lower = text.lower()

        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            scores[domain] = score

        # Find best match
        max_score = max(scores.values()) if scores else 0

        # If clear winner (score >= 3), use it
        if max_score >= 3:
            best_domain = max(scores, key=scores.get)
            logger.debug(f"Keyword match: {best_domain} (score: {max_score})")
            return best_domain

        # Step 2: LLM classification for ambiguous cases
        logger.debug("Ambiguous keywords, using LLM for classification")
        return self._llm_classify(text)

    def _llm_classify(self, text: str) -> str:
        """Classify domain using LLM (fallback for ambiguous cases)."""
        try:
            prompt = f"""Classify this conversation into one domain:
- coding: Software development, programming, debugging
- music: Music production, mixing, DAW, recording
- blender: 3D graphics, modeling, rendering, animation
- study: Research, learning, academic, notes
- general: Everything else

Text: {text[:500]}  # First 500 chars to save tokens

Answer with ONLY the domain name (coding, music, blender, study, or general):"""

            response = self.llm_client.generate(
                model=self.settings.model_primary,
                prompt=prompt,
                temperature=0.1,
            )

            domain = response.strip().lower()

            # Validate response
            valid_domains = ["coding", "music", "blender", "study", "general"]
            if domain not in valid_domains:
                logger.warning(f"LLM returned invalid domain: {domain}, using 'general'")
                return "general"

            logger.debug(f"LLM classified as: {domain}")
            return domain

        except Exception as e:
            logger.error(f"LLM classification failed: {e}, using 'general'")
            return "general"


class ChatHistoryIngester:
    """Ingest chat histories from multiple formats."""

    def __init__(self):
        """Initialize ingester."""
        self.domain_detector = DomainDetector()
        self.llm_client = OllamaClient()
        self.settings = get_settings()

    def ingest_file(self, filepath: str) -> List[dict]:
        """
        Ingest chat history from file (auto-detect format).

        Args:
            filepath: Path to chat export file

        Returns:
            List of normalized conversation dicts
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        # Auto-detect format by extension
        if filepath.suffix == ".json":
            return self.ingest_json(filepath)
        elif filepath.suffix == ".md":
            return self.ingest_markdown(filepath)
        else:
            raise ValueError(f"Unsupported format: {filepath.suffix}")

    def ingest_json(self, filepath: Path) -> List[dict]:
        """
        Ingest JSON chat export (GitHub Copilot, ChatGPT format).

        Expected format:
        {
          "conversations": [
            {
              "id": "...",
              "timestamp": "2026-01-15T14:30:00Z",
              "messages": [
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
              ]
            }
          ]
        }
        """
        logger.info(f"Ingesting JSON: {filepath}")

        with open(filepath, "r") as f:
            data = json.load(f)

        conversations = []

        # Handle both direct list and wrapped format
        conv_list = data if isinstance(data, list) else data.get("conversations", [])

        for i, conv in enumerate(conv_list):
            try:
                normalized = self._normalize_conversation(conv)
                conversations.append(normalized)

                if (i + 1) % 100 == 0:
                    logger.info(f"Processed {i + 1} conversations...")

            except Exception as e:
                logger.warning(f"Skipping malformed conversation {i}: {e}")
                continue

        logger.info(f"✅ Ingested {len(conversations)} conversations from {filepath}")
        return conversations

    def ingest_markdown(self, filepath: Path) -> List[dict]:
        """
        Ingest Markdown chat export (Discord, Slack, custom format).

        Expected format:
        # Conversation Title
        **User**: Question here
        **Assistant**: Answer here

        ---

        # Another Conversation
        ...
        """
        logger.info(f"Ingesting Markdown: {filepath}")

        with open(filepath, "r") as f:
            content = f.read()

        # Split by conversation markers
        conv_blocks = content.split("---\n")
        conversations = []

        for block in conv_blocks:
            if not block.strip():
                continue

            try:
                conv = self._parse_markdown_block(block)
                if conv and conv.get("messages"):
                    conversations.append(conv)
            except Exception as e:
                logger.warning(f"Skipping malformed markdown block: {e}")
                continue

        logger.info(f"✅ Ingested {len(conversations)} conversations from {filepath}")
        return conversations

    def _normalize_conversation(self, conv: dict) -> dict:
        """
        Normalize conversation to standard format.

        Args:
            conv: Raw conversation dict

        Returns:
            Normalized conversation with auto-detected domain and tags
        """
        # Extract fields with defaults
        conv_id = conv.get("id", "")
        timestamp = conv.get("timestamp", datetime.now().isoformat() + "Z")
        messages = conv.get("messages", [])

        # Reconstruct text for domain detection
        text_for_detection = " ".join(
            msg.get("content", "") for msg in messages
        )

        # Auto-detect domain
        domain = self.domain_detector.detect(text_for_detection)

        # Auto-generate tags
        tags = self._auto_tag(text_for_detection, domain)

        # Generate embedding
        embedding = self._generate_embedding(text_for_detection)

        return {
            "id": conv_id,
            "timestamp": timestamp,
            "participants": conv.get("participants", ["User", "AI"]),
            "domain": domain,
            "messages": messages,
            "tags": tags,
            "embedding": embedding,
        }

    def _parse_markdown_block(self, block: str) -> dict:
        """Parse a markdown conversation block."""
        lines = block.strip().split("\n")
        messages = []
        current_role = None
        current_content = []

        for line in lines:
            if line.startswith("**User**:"):
                if current_content and current_role:
                    messages.append({
                        "role": current_role,
                        "content": " ".join(current_content).strip()
                    })
                current_role = "user"
                current_content = [line.replace("**User**:", "").strip()]
            elif line.startswith("**Assistant**:"):
                if current_content and current_role:
                    messages.append({
                        "role": current_role,
                        "content": " ".join(current_content).strip()
                    })
                current_role = "assistant"
                current_content = [line.replace("**Assistant**:", "").strip()]
            elif current_role and line.strip():
                current_content.append(line.strip())

        # Add last message
        if current_content and current_role:
            messages.append({
                "role": current_role,
                "content": " ".join(current_content).strip()
            })

        return {
            "id": "",
            "timestamp": datetime.now().isoformat() + "Z",
            "messages": messages,
        }

    def _auto_tag(self, text: str, domain: str) -> List[str]:
        """
        Generate tags using LLM.

        Args:
            text: Conversation text
            domain: Detected domain

        Returns:
            List of relevant tags
        """
        try:
            prompt = f"""Extract 3-5 relevant tags from this text.
Domain: {domain}

Text: {text[:300]}

Return ONLY a JSON list of strings:
["tag1", "tag2", "tag3"]"""

            response = self.llm_client.generate(
                model=self.settings.model_primary,
                prompt=prompt,
                temperature=0.3,
            )

            # Parse JSON response
            import json
            tags = json.loads(response.strip())
            return tags if isinstance(tags, list) else [domain]

        except Exception as e:
            logger.warning(f"Auto-tagging failed: {e}, using domain as tag")
            return [domain]

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        try:
            embedding = self.llm_client.embed(
                model=self.settings.model_embedding,
                text=text[:1000],  # Limit to first 1000 chars
            )
            return embedding
        except Exception as e:
            logger.warning(f"Embedding generation failed: {e}")
            return []

    def ingest_and_store(self, filepath: str) -> int:
        """
        Ingest file and store in memory silos.

        Args:
            filepath: Path to chat export

        Returns:
            Number of conversations stored
        """
        conversations = self.ingest_file(filepath)

        # Organize by domain and store
        stored_count = 0

        for conv in conversations:
            domain = conv.get("domain", "general")
            try:
                memory = DomainMemory(domain)
                memory.add_conversation(conv)
                stored_count += 1
            except Exception as e:
                logger.error(f"Failed to store conversation: {e}")

        logger.info(f"✅ Stored {stored_count} conversations in memory silos")
        return stored_count
