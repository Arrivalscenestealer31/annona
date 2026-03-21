#!/bin/bash

# Akaion Runner - Startup Script

echo "🚀 Starting Akaion Runner..."

# Check if virtual environment exists
if [ ! -d "env" ]; then
    echo "❌ Virtual environment not found. Run install.sh first."
    exit 1
fi

# Activate virtual environment
source env/bin/activate

# Check if configured
if [ ! -f "$HOME/.akaion/auth.json" ]; then
    echo "⚠️  Runner not configured. Running setup..."
    python cli.py login
    python cli.py init
fi

# Start runner in daemon mode
echo "🔄 Starting daemon..."
python cli.py run --daemon

deactivate
