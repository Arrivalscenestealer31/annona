#!/bin/bash

# Akaion Runner - Startup Script
# Usa sempre l'interprete del venv direttamente per evitare conflitti con alias shell

set -e

PYTHON="$(dirname "$0")/env/bin/python3"

echo "Starting Akaion Runner..."

if [ ! -f "$PYTHON" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv env
    env/bin/pip install -r requirements.txt -q
fi

# Check if configured
if [ ! -f "$HOME/.akaion/auth.json" ]; then
    echo "Runner not configured. Running setup..."
    "$PYTHON" cli.py login
    "$PYTHON" cli.py init --no-interactive
fi

PORT="${PORT:-7070}"
BRAIN_DIR="${BRAIN_DIR:-$HOME/akaion-brain}"

echo "Port: $PORT  Brain: $BRAIN_DIR"
exec "$PYTHON" cli.py run --port "$PORT" --brain-dir "$BRAIN_DIR"
