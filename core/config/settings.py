"""
Core configuration settings for Local AI Agent.

Settings are loaded from environment variables with defaults.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Ollama Configuration
    ollama_endpoint: str = Field(
        default="http://localhost:11434",
        description="Ollama API endpoint",
    )
    ollama_timeout: int = Field(
        default=300,
        description="Ollama request timeout in seconds",
    )

    # Model Configuration
    model_primary: str = Field(
        default="qwen2.5-coder:7b",
        description="Primary model for code generation",
    )
    model_reasoning: str = Field(
        default="deepseek-r1:8b",
        description="Model for complex reasoning",
    )
    model_embedding: str = Field(
        default="nomic-embed-text",
        description="Model for text embeddings",
    )

    # Memory Configuration
    vector_db_path: Path = Field(
        default=Path("./chroma_data"),
        description="Path to ChromaDB storage",
    )
    max_memory_messages: int = Field(
        default=1000000,
        description="Maximum messages to store in memory",
    )

    # Debug/Development
    debug: bool = Field(
        default=False,
        description="Enable debug logging",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )

    def __init__(self, **data):
        super().__init__(**data)
        # Create directories if they don't exist
        self.vector_db_path.mkdir(parents=True, exist_ok=True)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def set_settings(settings: Settings) -> None:
    """Override global settings instance (for testing)."""
    global _settings
    _settings = settings
