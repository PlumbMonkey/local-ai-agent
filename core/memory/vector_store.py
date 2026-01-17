"""ChromaDB wrapper for vector storage."""

import logging
from pathlib import Path
from typing import Optional

from core.config.settings import get_settings

logger = logging.getLogger(__name__)


class VectorStore:
    """Wrapper for ChromaDB vector storage."""

    def __init__(self, path: Optional[Path] = None, collection_name: str = "default"):
        """
        Initialize vector store.

        Args:
            path: Path to ChromaDB data directory
            collection_name: Name of collection to use
        """
        settings = get_settings()
        self.path = path or settings.vector_db_path
        self.collection_name = collection_name
        self._client = None

    @property
    def client(self):
        """Lazy load ChromaDB client."""
        if self._client is None:
            try:
                import chromadb
                self._client = chromadb.PersistentClient(
                    path=str(self.path)
                )
            except ImportError:
                logger.error("chromadb not installed")
                raise
        return self._client

    def add_documents(
        self,
        documents: list[str],
        metadatas: Optional[list[dict]] = None,
        ids: Optional[list[str]] = None,
    ) -> None:
        """
        Add documents to vector store.

        Args:
            documents: List of document texts
            metadatas: Optional metadata for each document
            ids: Optional IDs for documents
        """
        try:
            collection = self.client.get_or_create_collection(
                name=self.collection_name
            )
            collection.add(
                documents=documents,
                metadatas=metadatas or [{}] * len(documents),
                ids=ids,
            )
            logger.info(f"Added {len(documents)} documents to vector store")
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise

    def query(
        self,
        query_text: str,
        n_results: int = 5,
    ) -> list[dict]:
        """
        Query vector store for similar documents.

        Args:
            query_text: Query text
            n_results: Number of results to return

        Returns:
            List of matching documents with metadata
        """
        try:
            collection = self.client.get_or_create_collection(
                name=self.collection_name
            )
            results = collection.query(
                query_texts=[query_text],
                n_results=n_results,
            )

            # Format results
            output = []
            if results and results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    output.append({
                        "document": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0,
                    })

            return output

        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []

    def get_collection_size(self) -> int:
        """Get number of documents in collection."""
        try:
            collection = self.client.get_or_create_collection(
                name=self.collection_name
            )
            return collection.count()
        except Exception as e:
            logger.error(f"Failed to get collection size: {e}")
            return 0

    def clear(self) -> None:
        """Clear all data from collection."""
        try:
            self.client.delete_collection(name=self.collection_name)
            logger.info(f"Cleared collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
