#!/bin/bash
# Compile requirements.txt from pyproject.toml using uv
# This is the recommended way to manage dependencies with uv

set -e

echo "🔒 Creating lock file from pyproject.toml..."
uv lock

echo "📦 Exporting lock file to requirements.txt..."
uv export --output-file requirements.txt

echo "✅ Requirements compiled successfully!"
echo "   Generated: requirements.txt"
