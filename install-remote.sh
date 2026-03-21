#!/bin/bash

# Akaion Runner - Remote Installation Script
# Usage: curl -fsSL https://install.akaion.com/runner.sh | bash

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
AKAION_REPO="https://github.com/akaion/akaion-runner.git"  # Modifica con il tuo repo
INSTALL_DIR="${AKAION_INSTALL_DIR:-$HOME/.akaion-runner}"
BIN_DIR="${AKAION_BIN_DIR:-$HOME/.local/bin}"
VERSION="${AKAION_VERSION:-main}"

# Functions
print_banner() {
    echo -e "${CYAN}"
    cat << "EOF"
    ___    __            _                 
   /   |  / /____  ___  (_)___  ____  
  / /| | / //_/ / / / __ \/ __ \/ __ \ 
 / ___ |/ ,< / /_/ / /_/ / / / / / / / 
/_/  |_/_/|_|\__,_/\____/_/ /_/_/ /_/  
                                        
    Runner Installation
EOF
    echo -e "${NC}"
}

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

check_requirements() {
    log_info "Checking system requirements..."
    
    # Check OS
    OS=$(uname -s)
    case "$OS" in
        Linux*)     PLATFORM="linux";;
        Darwin*)    PLATFORM="macos";;
        *)          
            log_error "Unsupported OS: $OS"
            exit 1
            ;;
    esac
    log_success "Platform: $PLATFORM"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not installed"
        log_info "Install Python 3.10+ from: https://www.python.org/"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    log_success "Python version: $PYTHON_VERSION"
    
    if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
        log_error "Python 3.10+ required. Current: $PYTHON_VERSION"
        exit 1
    fi
    
    # Check Git
    if ! command -v git &> /dev/null; then
        log_error "Git is required but not installed"
        exit 1
    fi
    log_success "Git: $(git --version | head -n1)"
    
    # Check UV
    if ! command -v uv &> /dev/null; then
        log_info "Installing UV (fast Python package installer)..."
        curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null 2>&1 || {
            log_error "Failed to install UV"
            exit 1
        }
        export PATH="$HOME/.cargo/bin:$PATH"
    fi
    log_success "UV: $(uv --version)"
}

install_runner() {
    log_info "Installing Akaion Runner..."
    
    # Create directories
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$BIN_DIR"
    mkdir -p "$HOME/.akaion"
    
    # Clone or update repository
    if [ -d "$INSTALL_DIR/.git" ]; then
        log_info "Updating existing installation..."
        cd "$INSTALL_DIR"
        git fetch --all
        git checkout "$VERSION"
        git pull origin "$VERSION"
    else
        log_info "Cloning repository..."
        rm -rf "$INSTALL_DIR"
        git clone --branch "$VERSION" "$AKAION_REPO" "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi
    
    log_success "Repository ready"
    
    # Create virtual environment with UV
    log_info "Creating virtual environment with UV..."
    if [ ! -d "$INSTALL_DIR/env" ]; then
        uv venv "$INSTALL_DIR/env"
    fi
    
    # Activate and install
    source "$INSTALL_DIR/env/bin/activate"
    
    log_info "Installing dependencies with UV..."
    uv pip install -e "$INSTALL_DIR" -q
    
    deactivate
    
    log_success "Dependencies installed"
}

create_executable() {
    log_info "Creating executable wrapper..."
    
    # Create akaion wrapper script
    cat > "$BIN_DIR/akaion" << 'WRAPPER'
#!/bin/bash
INSTALL_DIR="${AKAION_INSTALL_DIR:-$HOME/.akaion-runner}"
source "$INSTALL_DIR/env/bin/activate"
python "$INSTALL_DIR/cli.py" "$@"
deactivate
WRAPPER
    
    chmod +x "$BIN_DIR/akaion"
    log_success "Executable created: $BIN_DIR/akaion"
}

setup_shell() {
    log_info "Setting up shell integration..."
    
    # Detect shell
    SHELL_NAME=$(basename "$SHELL")
    
    case "$SHELL_NAME" in
        bash)
            SHELL_RC="$HOME/.bashrc"
            ;;
        zsh)
            SHELL_RC="$HOME/.zshrc"
            ;;
        fish)
            SHELL_RC="$HOME/.config/fish/config.fish"
            ;;
        *)
            log_warning "Unknown shell: $SHELL_NAME. Skipping shell integration."
            return
            ;;
    esac
    
    # Add to PATH if not already there
    if ! echo "$PATH" | grep -q "$BIN_DIR"; then
        if [ "$SHELL_NAME" = "fish" ]; then
            echo "set -gx PATH $BIN_DIR \$PATH" >> "$SHELL_RC"
        else
            echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$SHELL_RC"
        fi
        log_success "Added $BIN_DIR to PATH in $SHELL_RC"
    else
        log_success "PATH already configured"
    fi
}

create_systemd_service() {
    if [ "$PLATFORM" != "linux" ]; then
        return
    fi
    
    if ! command -v systemctl &> /dev/null; then
        return
    fi
    
    log_info "Creating systemd service (optional)..."
    
    SERVICE_FILE="$HOME/.config/systemd/user/akaion-runner.service"
    mkdir -p "$(dirname "$SERVICE_FILE")"
    
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Akaion Runner
After=network.target

[Service]
Type=simple
ExecStart=$BIN_DIR/akaion run --daemon
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF
    
    log_success "Systemd service created: $SERVICE_FILE"
    log_info "Enable with: systemctl --user enable akaion-runner"
    log_info "Start with: systemctl --user start akaion-runner"
}

create_launchd_service() {
    if [ "$PLATFORM" != "macos" ]; then
        return
    fi
    
    log_info "Creating LaunchAgent (optional)..."
    
    PLIST_FILE="$HOME/Library/LaunchAgents/com.akaion.runner.plist"
    mkdir -p "$(dirname "$PLIST_FILE")"
    
    cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.akaion.runner</string>
    <key>ProgramArguments</key>
    <array>
        <string>$BIN_DIR/akaion</string>
        <string>run</string>
        <string>--daemon</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$HOME/Library/Logs/akaion-runner.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/Library/Logs/akaion-runner.error.log</string>
</dict>
</plist>
EOF
    
    log_success "LaunchAgent created: $PLIST_FILE"
    log_info "Load with: launchctl load $PLIST_FILE"
}

post_install() {
    log_info "Running post-installation setup..."
    
    # Create config directory
    mkdir -p "$HOME/.akaion"
    
    # Copy default config if not exists
    if [ ! -f "$HOME/.akaion/config.yaml" ] && [ -f "$INSTALL_DIR/config.yaml" ]; then
        cp "$INSTALL_DIR/config.yaml" "$HOME/.akaion/config.yaml"
        log_success "Default config copied to ~/.akaion/config.yaml"
    fi
    
    # Create logs directory
    mkdir -p "$HOME/.akaion/logs"
}

print_next_steps() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}  ${CYAN}Akaion Runner installed successfully!${NC}                 ${GREEN}║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}📋 Next Steps:${NC}"
    echo ""
    echo -e "  1️⃣  ${CYAN}Reload your shell:${NC}"
    echo -e "     ${GREEN}source ~/.$(basename $SHELL)rc${NC}"
    echo ""
    echo -e "  2️⃣  ${CYAN}Authenticate:${NC}"
    echo -e "     ${GREEN}akaion login${NC}"
    echo ""
    echo -e "  3️⃣  ${CYAN}Initialize configuration:${NC}"
    echo -e "     ${GREEN}akaion init${NC}"
    echo ""
    echo -e "  4️⃣  ${CYAN}Start the runner:${NC}"
    echo -e "     ${GREEN}akaion run${NC}"
    echo ""
    echo -e "${YELLOW}📚 Documentation:${NC}"
    echo -e "  • Quick Start: ${BLUE}$INSTALL_DIR/QUICKSTART.md${NC}"
    echo -e "  • Architecture: ${BLUE}$INSTALL_DIR/ARCHITECTURE.md${NC}"
    echo -e "  • Check status: ${GREEN}akaion status${NC}"
    echo -e "  • View logs: ${GREEN}akaion logs${NC}"
    echo ""
    echo -e "${YELLOW}🔧 Optional - Auto-start on boot:${NC}"
    if [ "$PLATFORM" = "linux" ]; then
        echo -e "  ${GREEN}systemctl --user enable akaion-runner${NC}"
        echo -e "  ${GREEN}systemctl --user start akaion-runner${NC}"
    elif [ "$PLATFORM" = "macos" ]; then
        echo -e "  ${GREEN}launchctl load ~/Library/LaunchAgents/com.akaion.runner.plist${NC}"
    fi
    echo ""
    echo -e "${CYAN}Installation directory: ${NC}$INSTALL_DIR"
    echo -e "${CYAN}Executable: ${NC}$BIN_DIR/akaion"
    echo ""
}

cleanup_on_error() {
    log_error "Installation failed. Cleaning up..."
    # Don't remove installation directory to allow debugging
    exit 1
}

# Main installation flow
main() {
    trap cleanup_on_error ERR
    
    print_banner
    
    log_info "Starting Akaion Runner installation..."
    echo ""
    
    check_requirements
    echo ""
    
    install_runner
    echo ""
    
    create_executable
    echo ""
    
    setup_shell
    echo ""
    
    if [ "$PLATFORM" = "linux" ]; then
        create_systemd_service
        echo ""
    elif [ "$PLATFORM" = "macos" ]; then
        create_launchd_service
        echo ""
    fi
    
    post_install
    
    print_next_steps
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    log_error "Please do not run this script as root"
    exit 1
fi

# Run main installation
main
