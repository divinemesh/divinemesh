#!/bin/bash
# DivineMesh Android Installer (via Termux)
# "Be strong and courageous. Do not be afraid." - Joshua 1:9
#
# Requirements: Termux (https://termux.dev) installed on Android
#
# One-line install (paste into Termux):
#   curl -sSL https://divinemesh.com/install.sh/android | bash

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

echo -e "${CYAN}"
cat << 'BANNER'
  ╔════════════════════════════════════════╗
  ║      DivineMesh Android (Termux)       ║
  ║  "His word is a lamp unto my feet"     ║
  ║          Psalm 119:105                  ║
  ╚════════════════════════════════════════╝
BANNER
echo -e "${NC}"

# Verify Termux environment
if [ ! -d "/data/data/com.termux" ] && [ -z "${TERMUX_VERSION:-}" ]; then
    echo -e "${RED}[✗] This script requires Termux on Android.${NC}"
    echo "    Install Termux from: https://f-droid.org/packages/com.termux/"
    exit 1
fi

echo -e "${GREEN}[→] Updating Termux packages...${NC}"
pkg update -y && pkg upgrade -y

echo -e "${GREEN}[→] Installing dependencies...${NC}"
pkg install -y python git openssl-tool clang libffi

echo -e "${GREEN}[→] Installing pip dependencies...${NC}"
pip install --upgrade pip
pip install aiohttp websockets psutil web3 cryptography pyotp requests

echo -e "${GREEN}[→] Cloning DivineMesh...${NC}"
mkdir -p ~/.divinemesh
git clone --depth 1 https://github.com/divinemesh/divinemesh ~/.divinemesh/repo

# Create launcher
cat > ~/.divinemesh/divinemesh.sh << 'LAUNCHER'
#!/bin/bash
cd ~/.divinemesh/repo
exec python -m client.daemon "$@"
LAUNCHER
chmod +x ~/.divinemesh/divinemesh.sh

# Add alias
if ! grep -q "divinemesh" ~/.bashrc 2>/dev/null; then
    echo "alias divinemesh='~/.divinemesh/divinemesh.sh'" >> ~/.bashrc
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   DivineMesh Android Installation Complete!      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Register your node:"
echo -e "    ${CYAN}~/.divinemesh/divinemesh.sh register${NC}"
echo ""
echo "  Start daemon:"
echo -e "    ${CYAN}~/.divinemesh/divinemesh.sh start${NC}"
echo ""
echo "  NOTE: Android limits background processes."
echo "  Keep Termux in foreground or use a wake lock app"
echo "  for continuous compute sharing."
echo ""
echo '  "Let your light shine before others." - Matthew 5:16'
echo ""
