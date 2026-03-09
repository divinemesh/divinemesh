#!/usr/bin/env bash
# ┌─────────────────────────────────────────────────────────────────────────────┐
# │  DivineMesh Linux/macOS Installer                                           │
# │  "The Lord is my strength and my shield." - Psalm 28:7                      │
# │                                                                             │
# │  One-line install:                                                          │
# │    curl -sSL https://install.divinemesh.io | bash                           │
# └─────────────────────────────────────────────────────────────────────────────┘

set -euo pipefail

REPO="https://github.com/divinemesh/divinemesh"
VERSION="latest"
INSTALL_DIR="${HOME}/.divinemesh"
BIN_DIR="${HOME}/.local/bin"
DOCKER_COMPOSE_VERSION="2.24.0"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

banner() {
cat << 'EOF'
  ██████╗ ██╗██╗   ██╗██╗███╗   ██╗███████╗    ███╗   ███╗███████╗███████╗██╗  ██╗
  ██╔══██╗██║██║   ██║██║████╗  ██║██╔════╝    ████╗ ████║██╔════╝██╔════╝██║  ██║
  ██║  ██║██║██║   ██║██║██╔██╗ ██║█████╗      ██╔████╔██║█████╗  ███████╗███████║
  ██║  ██║██║╚██╗ ██╔╝██║██║╚██╗██║██╔══╝      ██║╚██╔╝██║██╔══╝  ╚════██║██╔══██║
  ██████╔╝██║ ╚████╔╝ ██║██║ ╚████║███████╗    ██║ ╚═╝ ██║███████╗███████║██║  ██║
  ╚═════╝ ╚═╝  ╚═══╝  ╚═╝╚═╝  ╚═══╝╚══════╝    ╚═╝     ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝

  "In the beginning was the Word, and the Word was with God" - John 1:1
  Distributed AI Compute Network | Powered by Faith & Cryptography
EOF
}

log_info()    { echo -e "${GREEN}[✓]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
log_error()   { echo -e "${RED}[✗]${NC} $*"; exit 1; }
log_step()    { echo -e "\n${CYAN}══>${NC} $*"; }

detect_os() {
    OS="$(uname -s)"
    ARCH="$(uname -m)"
    case "$OS" in
        Linux*)  PLATFORM="linux";;
        Darwin*) PLATFORM="macos";;
        *)       log_error "Unsupported OS: $OS. Use Windows installer.";;
    esac
    log_info "Platform: $PLATFORM ($ARCH)"
}

check_deps() {
    log_step "Checking dependencies..."
    local missing=()
    for cmd in curl git python3; do
        command -v "$cmd" &>/dev/null || missing+=("$cmd")
    done
    if [ ${#missing[@]} -gt 0 ]; then
        log_warn "Missing: ${missing[*]}"
        if [ "$PLATFORM" = "linux" ]; then
            sudo apt-get update -qq && sudo apt-get install -y -qq curl git python3 python3-pip python3-venv
        elif [ "$PLATFORM" = "macos" ]; then
            command -v brew &>/dev/null || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            brew install curl git python3
        fi
    fi
    log_info "All dependencies satisfied"
}

install_docker() {
    log_step "Installing Docker..."
    if command -v docker &>/dev/null; then
        log_info "Docker already installed: $(docker --version)"
        return
    fi
    if [ "$PLATFORM" = "linux" ]; then
        curl -fsSL https://get.docker.com | sh
        sudo usermod -aG docker "$USER"
        log_warn "Added $USER to docker group. You may need to log out and back in."
    elif [ "$PLATFORM" = "macos" ]; then
        log_warn "Please install Docker Desktop from https://docker.com/products/docker-desktop"
        log_warn "Then re-run this installer."
        exit 0
    fi
    # Install docker-compose v2
    mkdir -p "${BIN_DIR}"
    curl -SL "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" \
        -o "${BIN_DIR}/docker-compose"
    chmod +x "${BIN_DIR}/docker-compose"
    log_info "Docker Compose installed"
}

install_divinemesh() {
    log_step "Installing DivineMesh..."
    mkdir -p "${INSTALL_DIR}" "${BIN_DIR}"

    # Clone or update repo
    if [ -d "${INSTALL_DIR}/repo" ]; then
        log_info "Updating existing installation..."
        git -C "${INSTALL_DIR}/repo" pull --quiet
    else
        git clone --depth 1 "${REPO}" "${INSTALL_DIR}/repo" --quiet
        log_info "Repository cloned"
    fi

    # Create Python virtual environment
    python3 -m venv "${INSTALL_DIR}/venv"
    "${INSTALL_DIR}/venv/bin/pip" install --quiet --upgrade pip
    "${INSTALL_DIR}/venv/bin/pip" install --quiet -r "${INSTALL_DIR}/repo/requirements.txt"
    log_info "Python environment ready"

    # Create launcher script
    cat > "${BIN_DIR}/divinemesh" << LAUNCHER
#!/usr/bin/env bash
# DivineMesh Node Launcher
# 'I can do all this through him who gives me strength.' - Phil 4:13
export DIVINEMESH_HOME="${INSTALL_DIR}"
exec "${INSTALL_DIR}/venv/bin/python" -m client.daemon "\$@"
LAUNCHER
    chmod +x "${BIN_DIR}/divinemesh"

    # Add to PATH if needed
    if [[ ":$PATH:" != *":${BIN_DIR}:"* ]]; then
        SHELL_RC="${HOME}/.bashrc"
        [[ "$SHELL" == *"zsh"* ]] && SHELL_RC="${HOME}/.zshrc"
        echo "export PATH=\"\$PATH:${BIN_DIR}\"" >> "$SHELL_RC"
        log_warn "Added ${BIN_DIR} to PATH in ${SHELL_RC}. Run: source ${SHELL_RC}"
    fi

    # Create data directory
    mkdir -p "${INSTALL_DIR}/data"
    log_info "DivineMesh installed to ${INSTALL_DIR}"
}

create_systemd_service() {
    [ "$PLATFORM" != "linux" ] && return
    log_step "Creating systemd service..."
    cat > /tmp/divinemesh.service << SERVICE
[Unit]
Description=DivineMesh Compute Node
Documentation=https://docs.divinemesh.io
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${INSTALL_DIR}/repo
ExecStart=${BIN_DIR}/divinemesh start
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=DIVINEMESH_HOME=${INSTALL_DIR}

[Install]
WantedBy=multi-user.target
SERVICE
    if command -v systemctl &>/dev/null && [ "${EUID:-$(id -u)}" -eq 0 ]; then
        mv /tmp/divinemesh.service /etc/systemd/system/
        systemctl daemon-reload
        log_info "Systemd service installed. Enable with: sudo systemctl enable --now divinemesh"
    else
        log_warn "Systemd service file at /tmp/divinemesh.service — run as root to install"
    fi
}

print_next_steps() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   DivineMesh Installation Complete!                  ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "  Next steps:"
    echo "  1. Register your node (generates ID + password automatically):"
    echo "     ${CYAN}divinemesh register${NC}"
    echo ""
    echo "  2. Start the daemon:"
    echo "     ${CYAN}divinemesh start${NC}"
    echo ""
    echo "  3. Open dashboard:"
    echo "     ${CYAN}http://127.0.0.1:8080${NC}"
    echo ""
    echo '  "The Lord is my light and my salvation—whom shall I fear?" - Psalm 27:1'
    echo ""
}

main() {
    banner
    detect_os
    check_deps
    install_docker
    install_divinemesh
    create_systemd_service
    print_next_steps
}

main "$@"
