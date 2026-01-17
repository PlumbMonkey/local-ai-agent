"""Tests for OllamaClient."""

import pytest
from unittest.mock import patch, MagicMock
from core.llm.ollama import OllamaClient


class TestOllamaClient:
    """Test OllamaClient functionality."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return OllamaClient(endpoint="http://localhost:11434")

    def test_health_check_success(self, client):
        """Test successful health check."""
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            assert client.health_check() is True

    def test_health_check_failure(self, client):
        """Test failed health check."""
        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            assert client.health_check() is False

    def test_list_models(self, client):
        """Test listing models."""
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = {
                "models": [
                    {"name": "qwen2.5-coder:7b"},
                    {"name": "deepseek-r1:8b"},
                ]
            }
            models = client.list_models()
            assert models == ["qwen2.5-coder:7b", "deepseek-r1:8b"]
