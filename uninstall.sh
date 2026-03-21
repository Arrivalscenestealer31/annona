#!/bin/bash

# Akaion Runner - Uninstall Script

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
INSTALL_DIR="${AKAION_INSTALL_DIR:-$HOME/.akaion-runner}"
BIN_DIR="${AKAION_BIN_DIR:-$HOME/.local/bin}"

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

echo -e "${YELLOW}"
cat << "EOF"
╔═══════════════════════════════════════╗
║  Akaion Runner Uninstaller            ║
╚═══════════════════════════════════════╝
EOF
echo -e "${NC}"

# Confirm uninstallation
read -p "Are you sure you want to uninstall Akaion Runner? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Uninstallation cancelled"
    exit 0
fi

# Ask about config
echo ""
read -p "Remove configuration files (~/.akaion)? (y/N) " -n 1 -r
echo
REMOVE_CONFIG=$REPLY

# Stop running services
log_info "Stopping services..."

# Linux systemd
if command -v systemctl &> /dev/null; then
    if systemctl --user is-active akaion-runner &> /dev/null; then
        systemctl --user stop akaion-runner || true
        log_success "Stopped systemd service"
    fi
    if systemctl --user is-enabled akaion-runner &> /dev/null; then
        systemctl --user disable akaion-runner || true
        log_success "Disabled systemd service"
    fi
    rm -f "$HOME/.config/systemd/user/akaion-runner.service"
fi

# macOS launchd
if [[ "$OSTYPE" == "darwin"* ]]; then
    PLIST="$HOME/Library/LaunchAgents/com.akaion.runner.plist"
    if [ -f "$PLIST" ]; then
        launchctl unload "$PLIST" 2>/dev/null || true
        rm -f "$PLIST"
        log_success "Removed LaunchAgent"
    fi
fi

# Remove executable
log_info "Removing executable..."
rm -f "$BIN_DIR/akaion"
log_success "Removed $BIN_DIR/akaion"

# Remove installation directory
log_info "Removing installation directory..."
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    log_success "Removed $INSTALL_DIR"
fi

# Remove configuration (if requested)
if [[ $REMOVE_CONFIG =~ ^[Yy]$ ]]; then
    log_info "Removing configuration..."
    if [ -d "$HOME/.akaion" ]; then
        rm -rf "$HOME/.akaion"
        log_success "Removed ~/.akaion"
    fi
else
    log_info "Configuration preserved in ~/.akaion"
fi

# Clean shell config
log_info "Cleaning shell configuration..."
for RC in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.config/fish/config.fish"; do
    if [ -f "$RC" ]; then
        # Remove PATH additions (backup first)
        if grep -q "$BIN_DIR" "$RC" 2>/dev/null; then
            cp "$RC" "$RC.akaion.bak"
            grep -v "$BIN_DIR" "$RC.akaion.bak" > "$RC" || true
            rm "$RC.akaion.bak"
            log_success "Cleaned $(basename $RC)"
        fi
    fi
done

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║${NC}  Akaion Runner uninstalled            ${GREEN}║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""

if [[ ! $REMOVE_CONFIG =~ ^[Yy]$ ]]; then
    log_info "Your configuration was preserved in ~/.akaion"
    log_info "Remove manually with: rm -rf ~/.akaion"
fi

echo ""
log_info "Reload your shell with: source ~/.$(basename $SHELL)rc"
echo ""
