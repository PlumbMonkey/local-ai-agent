#!/usr/bin/env python
"""One-command setup for Local AI Agent (Windows)."""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, description):
    """Run command and report result."""
    print(f"\n➤ {description}")
    try:
        subprocess.run(cmd, shell=True, check=True)
        print(f"✅ {description}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description}: {e}")
        return False


def main():
    """Main setup routine."""
    print("🚀 Local AI Agent Setup")
    print("=" * 50)

    # Check Python version
    if sys.version_info < (3, 11):
        print(f"❌ Python 3.11+ required (found {sys.version_info.major}.{sys.version_info.minor})")
        return 1

    # Create virtual environment
    if not Path("venv").exists():
        if not run_command("python -m venv venv", "Create virtual environment"):
            return 1
    else:
        print("✅ Virtual environment already exists")

    # Activate venv (Windows)
    venv_activate = Path("venv/Scripts/python.exe")
    if not venv_activate.exists():
        print(f"❌ Virtual environment not found at {venv_activate}")
        return 1

    # Install dependencies
    pip_cmd = str(venv_activate).replace("python.exe", "pip.exe")
    if not run_command(f"{pip_cmd} install -e \".[dev]\"", "Install dependencies"):
        return 1

    print("\n" + "=" * 50)
    print("✅ Setup complete!")
    print("\n📝 Next steps:")
    print("1. Activate virtual environment:")
    print("   venv\\Scripts\\activate")
    print("\n2. Start Ollama:")
    print("   ollama serve")
    print("\n3. Pull models (in another terminal):")
    print("   ollama pull qwen2.5-coder:7b")
    print("   ollama pull nomic-embed-text")
    print("\n4. Start the CLI:")
    print("   python -m interfaces.cli.main")
    print("\n📚 Documentation:")
    print("   - Setup: docs/SETUP.md")
    print("   - Architecture: docs/ARCHITECTURE.md")
    print("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())
