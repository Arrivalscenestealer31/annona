#!/bin/bash

# Akaion Runner - Installation Script

echo "📦 Installing Akaion Runner..."

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.10"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"; then
    echo "❌ Python 3.10+ required. Current version: $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python version: $PYTHON_VERSION"

# Check/Install UV
if ! command -v uv &> /dev/null; then
    echo "📦 Installing UV (fast Python package installer)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

echo "✅ UV: $(uv --version)"

# Create virtual environment with UV
if [ ! -d "env" ]; then
    echo "🔧 Creating virtual environment with UV..."
    uv venv env
fi

# Activate virtual environment
source env/bin/activate

# Install dependencies with UV
echo "📥 Installing dependencies with UV..."
uv pip install -e .

# Create logs directory
mkdir -p logs

# Create .akaion directory
mkdir -p ~/.akaion

# Create executable in ~/.local/bin
echo "🔗 Creating akaion command..."
mkdir -p ~/.local/bin

INSTALL_DIR="$(pwd)"
cat > ~/.local/bin/akaion << EOF
#!/bin/bash
source "$INSTALL_DIR/env/bin/activate"
python "$INSTALL_DIR/cli.py" "\$@"
deactivate
EOF

chmod +x ~/.local/bin/akaion

# Add to PATH if not already there
if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo ""
    echo "⚠️  Adding ~/.local/bin to PATH..."
    
    # Detect shell and add to appropriate rc file
    if [ -n "$BASH_VERSION" ]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
        echo "   Added to ~/.bashrc"
    elif [ -n "$ZSH_VERSION" ]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
        echo "   Added to ~/.zshrc"
    fi
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "📍 Next steps:"
echo ""
if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo "1. Reload your shell:"
    echo "   source ~/.bashrc   # or ~/.zshrc"
    echo ""
    echo "2. Run: akaion login"
else
    echo "1. Run: akaion login"
fi
echo "3. Run: akaion init"
echo "4. Run: akaion run"
echo ""
echo "Or use the start script: ./start.sh"

deactivate
