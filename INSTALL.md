# Akaion Runner - Installation Guide

## 🚀 Quick Install (Recommended)

### One-Line Installation

```bash
curl -fsSL https://install.akaion.com/runner.sh | bash
```

Or with wget:

```bash
wget -qO- https://install.akaion.com/runner.sh | bash
```

### What it does:
1. ✅ Checks system requirements (Python 3.10+, Git)
2. ✅ Clones the repository
3. ✅ Creates virtual environment
4. ✅ Installs dependencies
5. ✅ Creates `akaion` command in PATH
6. ✅ Sets up shell integration
7. ✅ Creates systemd/launchd service (optional)

---

## 📦 Manual Installation

### Prerequisites
- Python 3.10 or higher
- Git
- pip

### Step 1: Clone Repository
```bash
git clone https://github.com/akaion/akaion-runner.git ~/.akaion-runner
cd ~/.akaion-runner
```

### Step 2: Install
```bash
./install.sh
```

### Step 3: Add to PATH
```bash
# For bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# For zsh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# For fish
set -Ua fish_user_paths $HOME/.local/bin
```

### Step 4: Verify Installation
```bash
akaion version
```

---

## 🎯 Platform-Specific Instructions

### Linux (Ubuntu/Debian)

```bash
# Install prerequisites
sudo apt update
sudo apt install -y python3.10 python3-pip python3-venv git curl

# Install Akaion Runner
curl -fsSL https://install.akaion.com/runner.sh | bash

# Reload shell
source ~/.bashrc

# Authenticate
akaion login
akaion init
akaion run
```

### macOS

```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install prerequisites
brew install python@3.11 git

# Install Akaion Runner
curl -fsSL https://install.akaion.com/runner.sh | bash

# Reload shell
source ~/.zshrc

# Authenticate
akaion login
akaion init
akaion run
```

### Windows (WSL2)

```bash
# Install WSL2 first (PowerShell as Administrator)
wsl --install

# Then follow Linux instructions inside WSL
```

---

## 🔧 Advanced Installation Options

### Custom Installation Directory

```bash
export AKAION_INSTALL_DIR="$HOME/my-custom-path"
curl -fsSL https://install.akaion.com/runner.sh | bash
```

### Specific Version

```bash
export AKAION_VERSION="v1.0.0"
curl -fsSL https://install.akaion.com/runner.sh | bash
```

### From Source (Development)

```bash
git clone https://github.com/akaion/akaion-runner.git
cd akaion-runner
python3 -m venv env
source env/bin/activate
pip install -e .
```

---

## 🐳 Docker Installation

### Pull Image
```bash
docker pull akaion/runner:latest
```

### Run Container
```bash
docker run -d \
  --name akaion-runner \
  -e AKAION_API_KEY=your_api_key \
  -v ~/.akaion:/root/.akaion \
  akaion/runner:latest
```

### Docker Compose
```yaml
version: '3.8'
services:
  akaion-runner:
    image: akaion/runner:latest
    container_name: akaion-runner
    environment:
      - AKAION_API_KEY=${AKAION_API_KEY}
    volumes:
      - ~/.akaion:/root/.akaion
    restart: unless-stopped
```

---

## 🔄 Auto-Start Setup

### Linux (systemd)

```bash
# Enable service
systemctl --user enable akaion-runner

# Start service
systemctl --user start akaion-runner

# Check status
systemctl --user status akaion-runner

# View logs
journalctl --user -u akaion-runner -f
```

### macOS (launchd)

```bash
# Load LaunchAgent
launchctl load ~/Library/LaunchAgents/com.akaion.runner.plist

# Check status
launchctl list | grep akaion

# View logs
tail -f ~/Library/Logs/akaion-runner.log
```

---

## 🔐 Post-Installation Setup

### 1. Authenticate
```bash
akaion login
# Enter your API key from https://dashboard.akaion.com
```

### 2. Initialize Configuration
```bash
akaion init
# Follow interactive prompts to configure permissions
```

### 3. Test Installation
```bash
# Check status
akaion status

# Run once
akaion run --once --task "Echo test"

# Start daemon
akaion run
```

---

## 🔍 Verify Installation

### Check Components
```bash
# Version
akaion version

# Status
akaion status --verbose

# Configuration
akaion config --show

# Test connectivity
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://api.akaion.com/health
```

### Directory Structure
```
~/.akaion-runner/          # Installation directory
├── cli.py
├── runner/
├── env/                   # Virtual environment
└── ...

~/.akaion/                 # User configuration
├── config.yaml
├── auth.json              # Encrypted credentials
└── logs/
    └── runner.log

~/.local/bin/
└── akaion                 # Executable symlink
```

---

## 🛠️ Troubleshooting

### Command not found: akaion

```bash
# Check if in PATH
echo $PATH | grep .local/bin

# Add to PATH manually
export PATH="$HOME/.local/bin:$PATH"

# Make permanent
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Python version error

```bash
# Check Python version
python3 --version

# Install Python 3.10+ (Ubuntu)
sudo apt install python3.10 python3.10-venv

# Update alternatives
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1
```

### Permission denied errors

```bash
# Make scripts executable
chmod +x ~/.akaion-runner/install.sh
chmod +x ~/.local/bin/akaion

# Fix ownership
chown -R $USER:$USER ~/.akaion-runner
chown -R $USER:$USER ~/.akaion
```

### Installation script fails

```bash
# Enable debug mode
bash -x <(curl -fsSL https://install.akaion.com/runner.sh)

# Or manual installation
git clone https://github.com/akaion/akaion-runner.git
cd akaion-runner
./install.sh
```

---

## 🗑️ Uninstallation

### Quick Uninstall
```bash
curl -fsSL https://install.akaion.com/uninstall.sh | bash
```

### Manual Uninstall
```bash
# Stop services
systemctl --user stop akaion-runner
systemctl --user disable akaion-runner

# Remove files
rm -rf ~/.akaion-runner
rm -rf ~/.akaion  # Optional: removes config
rm ~/.local/bin/akaion
```

---

## 📊 Installation Verification Checklist

- [ ] Python 3.10+ installed
- [ ] Git installed
- [ ] Repository cloned successfully
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] `akaion` command available
- [ ] Authentication successful
- [ ] Configuration initialized
- [ ] Runner starts without errors
- [ ] Can connect to cloud backend

---

## 🆘 Support

If you encounter issues:

1. Check [Troubleshooting](#troubleshooting) section
2. View logs: `akaion logs --tail 100`
3. Check status: `akaion status --verbose`
4. Report issues: https://github.com/akaion/akaion-runner/issues

---

## 📚 Next Steps

After installation:
- Read [QUICKSTART.md](QUICKSTART.md) for usage guide
- Check [ARCHITECTURE.md](ARCHITECTURE.md) for technical details
- Configure permissions in `~/.akaion/config.yaml`
- Set up auto-start with systemd/launchd
