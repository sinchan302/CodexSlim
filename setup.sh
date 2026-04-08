#!/usr/bin/env bash

# CodexSlim One-Click Setup Script
# This script sets up a virtual environment and installs CodexSlim for immediate use.

set -e

echo "======================================"
echo "    🚀 Setting up CodexSlim v1...     "
echo "======================================"

# 1. Ensure Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 could not be found."
    echo "Please install Python 3.9+ to run CodexSlim."
    exit 1
fi

# 2. Check for the .venv directory
if [ -d ".venv" ]; then
    echo "♻️  Virtual environment already exists in .venv/"
else
    echo "📦 Creating virtual environment (.venv)..."
    python3 -m venv .venv
fi

# 3. Activate the virtual environment
echo "🔄 Activating virtual environment..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    # Windows
    source .venv/Scripts/activate
else
    # macOS / Linux
    source .venv/bin/activate
fi

# 4. Upgrade pip automatically
echo "⬆️  Upgrading pip..."
pip install --upgrade pip --quiet

# 5. Install the package in editable mode with development dependencies
echo "⚙️  Installing CodexSlim and dependencies..."
pip install -e '.[dev]' --quiet

# 6. Verify Installation
echo "✅ Installation complete!"
echo ""
echo "======================================"
echo "          🎉 Ready to use!           "
echo "======================================"
echo "To activate the environment and start slimming, run:"
echo ""
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    echo "    source .venv/Scripts/activate"
else
    echo "    source .venv/bin/activate"
fi
echo "    slim --help"
echo ""
echo "Try running a quick test:"
echo "    slim ./codexslim --format manifest --out SLIM.md"
echo "======================================"
