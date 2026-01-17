"""Test fixtures and utilities."""

import pytest
from core.config.settings import Settings, set_settings
from pathlib import Path
import tempfile


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_settings(temp_dir):
    """Create settings with temporary paths."""
    settings = Settings(vector_db_path=temp_dir / "chroma_data")
    set_settings(settings)
    yield settings
