#!/usr/bin/env bash
# Launches the Native Desktop GUI Application for Transaction Dispute & Fraud Triage Copilot
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Ensure offline environment variables for fast, deterministic local execution
export FORCE_OFFLINE=1
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

# Check for virtualenv
VENV_PYTHON="$DIR/case-study-4/.venv/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    echo "Virtual environment not found at $VENV_PYTHON."
    echo "Please run: cd case-study-4 && python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt"
    exit 1
fi

echo "=========================================================="
echo " Starting Native Desktop Copilot (macOS Tkinter GUI)..."
echo " Window will open on your desktop directly."
echo "=========================================================="

exec "$VENV_PYTHON" "$DIR/desktop_app.py" "$@"
