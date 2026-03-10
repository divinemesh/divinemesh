#!/bin/bash
# ============================================================
#  DivineMesh Node — One-Line Installer
#  curl -sSL https://divinemesh.com/install.sh | bash
# ============================================================
set -e

REPO="https://github.com/divinemesh/divinemesh"
COORDINATOR="https://coordinator.divinemesh.com"
INSTALL_DIR="$HOME/.divinemesh"
BIN_DIR="$HOME/.local/bin"
PYTHON_MIN="3.10"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; GOLD='\033[0;33m'; NC='\033[0m'; BOLD='\033[1m'

banner() {
  echo ""
  echo -e "${GOLD}╔══════════════════════════════════════════════════════╗${NC}"
  echo -e "${GOLD}║          ✝  DivineMesh Node Installer  ✝             ║${NC}"
  echo -e "${GOLD}║   'For where two or three gather in my name...'      ║${NC}"
  echo -e "${GOLD}║                    — Matthew 18:20                   ║${NC}"
  echo -e "${GOLD}╚══════════════════════════════════════════════════════╝${NC}"
  echo ""
}

info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
step()    { echo -e "\n${BOLD}${GOLD}>>> $1${NC}"; }

banner

# ── Detect OS ────────────────────────────────────────────────
step "Detecting your system..."
OS="$(uname -s)"
ARCH="$(uname -m)"
info "OS: $OS | Arch: $ARCH"

case "$OS" in
  Linux*)  PLATFORM="linux" ;;
  Darwin*) PLATFORM="macos" ;;
  *)       error "Unsupported OS: $OS. Use Windows installer or Docker." ;;
esac
success "Platform: $PLATFORM"

# ── Check Python ─────────────────────────────────────────────
step "Checking Python..."
PYTHON=""
for cmd in python3 python3.12 python3.11 python3.10; do
  if command -v "$cmd" &>/dev/null; then
    VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    MAJ=$(echo "$VER" | cut -d. -f1); MIN=$(echo "$VER" | cut -d. -f2)
    if [ "$MAJ" -ge 3 ] && [ "$MIN" -ge 10 ]; then
      PYTHON="$cmd"; success "Found Python $VER ($cmd)"; break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  warn "Python 3.10+ not found. Installing..."
  if [ "$PLATFORM" = "linux" ]; then
    if command -v apt-get &>/dev/null; then
      sudo apt-get update -qq && sudo apt-get install -y python3 python3-pip python3-venv
    elif command -v yum &>/dev/null; then
      sudo yum install -y python3 python3-pip
    elif command -v pacman &>/dev/null; then
      sudo pacman -Sy --noconfirm python python-pip
    else
      error "Cannot install Python automatically. Please install Python 3.10+ manually from python.org"
    fi
  elif [ "$PLATFORM" = "macos" ]; then
    if command -v brew &>/dev/null; then
      brew install python3
    else
      error "Please install Homebrew first: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    fi
  fi
  PYTHON="python3"
fi

# ── Check Git ────────────────────────────────────────────────
step "Checking Git..."
if ! command -v git &>/dev/null; then
  warn "Git not found. Installing..."
  if command -v apt-get &>/dev/null; then sudo apt-get install -y git
  elif command -v yum &>/dev/null; then sudo yum install -y git
  elif command -v brew &>/dev/null; then brew install git
  else error "Please install Git from git-scm.com"; fi
fi
success "Git found: $(git --version)"

# ── Download DivineMesh ──────────────────────────────────────
step "Downloading DivineMesh..."
mkdir -p "$INSTALL_DIR"

if [ -d "$INSTALL_DIR/repo" ]; then
  info "Existing install found. Updating..."
  cd "$INSTALL_DIR/repo" && git pull origin main
else
  info "Cloning from GitHub..."
  git clone "$REPO" "$INSTALL_DIR/repo"
fi
success "DivineMesh downloaded to $INSTALL_DIR/repo"

# ── Create Virtual Environment ───────────────────────────────
step "Setting up Python environment..."
cd "$INSTALL_DIR/repo"
$PYTHON -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"
pip install --upgrade pip -q
pip install -r requirements.txt -q
success "Python environment ready"

# ── Create Launcher Script ───────────────────────────────────
step "Creating launcher..."
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/divinemesh" << LAUNCHER
#!/bin/bash
source "$INSTALL_DIR/venv/bin/activate"
cd "$INSTALL_DIR/repo"
python -m client.daemon "\$@"
LAUNCHER
chmod +x "$BIN_DIR/divinemesh"

# ── Create systemd Service (Linux only) ─────────────────────
if [ "$PLATFORM" = "linux" ] && command -v systemctl &>/dev/null; then
  step "Creating system service (auto-start on boot)..."
  SERVICE_FILE="$HOME/.config/systemd/user/divinemesh.service"
  mkdir -p "$(dirname $SERVICE_FILE)"
  cat > "$SERVICE_FILE" << SERVICE
[Unit]
Description=DivineMesh Node
After=network.target
Documentation=https://divinemesh.com

[Service]
Type=simple
ExecStart=$BIN_DIR/divinemesh start
Restart=always
RestartSec=10
Environment=DIVINEMESH_COORDINATOR=$COORDINATOR

[Install]
WantedBy=default.target
SERVICE
  systemctl --user daemon-reload
  systemctl --user enable divinemesh
  success "System service created (will auto-start on boot)"
fi

# ── Add to PATH ──────────────────────────────────────────────
step "Setting up PATH..."
SHELL_RC=""
case "$SHELL" in
  */bash) [ -f "$HOME/.bashrc" ] && SHELL_RC="$HOME/.bashrc" || SHELL_RC="$HOME/.bash_profile" ;;
  */zsh)  SHELL_RC="$HOME/.zshrc" ;;
  *)      SHELL_RC="$HOME/.profile" ;;
esac

if [ -n "$SHELL_RC" ] && ! grep -q "divinemesh" "$SHELL_RC" 2>/dev/null; then
  echo "" >> "$SHELL_RC"
  echo "# DivineMesh" >> "$SHELL_RC"
  echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$SHELL_RC"
  success "Added to PATH in $SHELL_RC"
fi

export PATH="$BIN_DIR:$PATH"

# ── First Run ────────────────────────────────────────────────
step "Setting up your node identity..."
cd "$INSTALL_DIR/repo"
source "$INSTALL_DIR/venv/bin/activate"
python -m client.daemon register

echo ""
echo -e "${GOLD}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GOLD}║          ✝  Installation Complete!  ✝                ║${NC}"
echo -e "${GOLD}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GOLD}║${NC}                                                      ${GOLD}║${NC}"
echo -e "${GOLD}║${NC}  Start your node:   ${GREEN}divinemesh start${NC}                ${GOLD}║${NC}"
echo -e "${GOLD}║${NC}  Check status:      ${GREEN}divinemesh status${NC}               ${GOLD}║${NC}"
echo -e "${GOLD}║${NC}  View earnings:     ${GREEN}divinemesh earnings${NC}             ${GOLD}║${NC}"
echo -e "${GOLD}║${NC}  Stop node:         ${GREEN}divinemesh stop${NC}                 ${GOLD}║${NC}"
echo -e "${GOLD}║${NC}                                                      ${GOLD}║${NC}"
echo -e "${GOLD}║${NC}  Dashboard:  ${BLUE}https://divinemesh.com${NC}                 ${GOLD}║${NC}"
echo -e "${GOLD}║${NC}  Network:    ${BLUE}https://coordinator.divinemesh.com${NC}      ${GOLD}║${NC}"
echo -e "${GOLD}║${NC}                                                      ${GOLD}║${NC}"
echo -e "${GOLD}║${NC}  'Give, and it will be given to you.' — Luke 6:38  ${GOLD}║${NC}"
echo -e "${GOLD}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}NOTE: Run 'source $SHELL_RC' or open a new terminal to use 'divinemesh' command.${NC}"
echo ""
