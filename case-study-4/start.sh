#!/usr/bin/env bash
# Quick-start launcher for the Fraud-Triage Copilot
# Usage:
#   ./start.sh          # Launches the Native Desktop GUI Window
#   ./start.sh --gui    # Launches the Native Desktop GUI Window
#   ./start.sh --web    # Launches the Web UI at http://localhost:8080
#   ./start.sh --cli    # Launches the Rich terminal interactive CLI

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$DIR/.." && pwd)"
cd "$DIR"

# Ensure offline embeddings safety
export FORCE_OFFLINE=1
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    ./.venv/bin/pip install -r requirements.txt
fi

if [ "$1" == "--cli" ]; then
    echo "Starting Interactive Terminal Copilot..."
    ./.venv/bin/python cli.py interactive
elif [ "$1" == "--web" ]; then
    echo "Starting Fraud-Triage Copilot Web UI..."
    echo "Opening http://localhost:8080 in your browser..."
    ./.venv/bin/python cli.py web --port 8080
else
    echo "Starting Native Desktop Copilot Window..."
    exec ./.venv/bin/python "$ROOT_DIR/desktop_app.py" "$@"
fi
