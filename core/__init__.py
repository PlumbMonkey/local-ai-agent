"""
Local AI Agent - Core Module

Privacy-first, self-hosted AI agent core implementation.
All code in this module is MIT Licensed.
"""

__version__ = "0.1.0"
__author__ = "PlumbMonkey"

from core.config.settings import Settings
from core.llm.ollama import OllamaClient

__all__ = [
    "Settings",
    "OllamaClient",
]
