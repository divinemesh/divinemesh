# ⚔ DivineMesh Network

> *"In the beginning was the Word, and the Word was with God, and the Word was God."* — John 1:1  
> *"Jesus Christ is the same yesterday and today and forever."* — Hebrews 13:8

**DivineMesh** is a decentralized distributed computing network where participants earn **DivineMesh Coin (DMC)** by lending idle CPU/GPU/RAM to AI and heavy-compute workloads. Encrypted with the Word. Secured by the Rock.

---

## ✦ Core Features

| Feature | Description |
|---|---|
| **Zero PII** | No email, phone, or name required. Identity is cryptographic only. |
| **Biblical Encryption** | AES-256-GCM + RSA-4096 seeded with 12 sacred Bible verses as entropy |
| **Blockchain Identity** | Node IDs, IP hashes, and MAC hashes stored on-chain (Polygon) |
| **Earn DMC** | Compute work → on-chain Merkle proof → DMC token reward |
| **Anti-Abuse** | Max 10 MAC addresses per IP · VPN detection & rejection |
| **Docker Sandbox** | Tasks run in read-only containers with seccomp + no-new-privileges |
| **No Data Stored** | Worker nodes never write task data to disk (tmpfs RAM only) |
| **Community Projects** | Users post AI projects; investors donate compute for a profit share |
| **2FA Support** | Optional TOTP two-factor authentication |
| **Cross-Platform** | Linux · macOS · Windows · Android |

---

## ⚡ One-Line Install

### Linux / macOS
```bash
curl -sSL https://install.divinemesh.io | bash
```

### Windows (PowerShell as Administrator)
```powershell
irm https://install.divinemesh.io/windows | iex
```

### Docker (any platform)
```bash
docker run -d \
  --name divinemesh-node \
  --security-opt no-new-privileges:true \
  --read-only \
  -v ~/.divinemesh/data:/app/data \
  -p 127.0.0.1:7474:7474 \
  divinemesh/node:latest start
```

### Docker Compose (recommended)
```bash
git clone https://github.com/divinemesh/divinemesh
cd divinemesh/docker
docker compose up -d
```

---

## 🚀 Quick Start

```bash
# 1. Register your node (generates ID + password, no personal info needed)
divinemesh register

# 2. Start the daemon
divinemesh start

# 3. Check status
divinemesh status

# 4. View earnings
divinemesh balance

# 5. Enable 2FA
divinemesh 2fa
```

**Dashboard:** Open `http://127.0.0.1:8080` in your browser.

---

## 🔐 Security Architecture

```
User System
└── Docker Container (read-only root, no-new-privileges, seccomp)
    ├── DivineMesh Daemon (Python, non-root user)
    │   ├── Task Sandbox (subprocess, tmpfs RAM only, no disk writes)
    │   ├── AES-256-GCM Encryption (Biblical entropy seeds)
    │   ├── RSA-4096 Node Signing
    │   └── Local REST API (127.0.0.1 only)
    └── Identity Store (~/.divinemesh/identity.enc)
        └── PBKDF2-HMAC-SHA512 (600,000 iterations + Bible salt)
```

### Biblical Entropy Sources
All cryptographic operations are seeded with 12 Bible verses combined with OS entropy:
- Genesis 1:1 · John 3:16 · John 14:6 · Psalm 23:1 · Philippians 4:13
- John 1:14 · Hebrews 13:8 · Joshua 1:9 · Proverbs 3:5 · Psalm 27:1
- John 11:25 · Jeremiah 29:11 · + Alpha & Omega (Revelation 1:8)

---

## 💰 DMC Token Economics

| Parameter | Value |
|---|---|
| Token Name | DivineMesh Coin |
| Symbol | DMC |
| Network | Polygon (EVM-compatible) |
| Max Supply | 144,000,000 DMC (Rev 7:4) |
| Reward Formula | `CPU_sec + 4×GPU_sec + 0.5×RAM_GB·hr` |

### Profit Distribution (Platform Fees)
```
Primary Account  ──── 50%  (Operations)
Reserve Account  ──── 30%  (Development & Reserve)
Tithe Account    ──── 20%  (Community & Charity)
```
All three accounts are controlled by the platform owner.

---

## 💳 Payment Methods

DMC can be purchased or earned via:
- Bitcoin (BTC)
- Ethereum (ETH)
- USDT / USDC (stablecoins)
- Credit / Debit Card
- PayPal
- Bank Wire Transfer

DMC is transferable to any EVM-compatible wallet (MetaMask, Trust Wallet, Coinbase Wallet, etc.)

---

## 🏗 Project Investment System

1. **Any user** can post a compute project with a title, description, and target compute units
2. **Investors** donate CPU/GPU time to funded projects
3. **Profit shares** are calculated proportionally to compute donated
4. **Project owner** always holds ≥ 51% authority (non-dilutable)
5. **Investor shares** are rebalanced on-chain as more compute is donated
6. **User agreements** are signed cryptographically on-chain before compute donation

---

## 🔒 Anti-Abuse System

| Rule | Enforcement |
|---|---|
| No VPN spoofing | Network adapter detection + on-chain VPN oracle |
| Max 10 MACs per IP | On-chain MAC registry with hard cap |
| No data stored on donor | tmpfs only, container tmpfs wiped on exit |
| Single account per IP | On-chain IP hash uniqueness check |
| No personal data | Only cryptographic hashes stored anywhere |

---

## 📁 Project Structure

```
divinemesh/
├── client/
│   ├── daemon.py          # Main node daemon + local REST API
│   ├── auth.py            # Identity management (no PII)
│   ├── encryption.py      # AES-256-GCM + Biblical entropy
│   ├── blockchain.py      # DMC wallet + on-chain interactions
│   ├── hardware_monitor.py# CPU/GPU/RAM monitoring + task sandbox
│   └── worker.py          # Isolated compute worker (RAM-only)
├── contracts/
│   └── DivineMesh.sol     # ERC-20 DMC + Registry + Projects (Solidity)
├── dashboard/
│   └── index.html         # Full web dashboard
├── docker/
│   ├── Dockerfile         # Hardened container
│   ├── docker-compose.yml # Full stack compose
│   └── security/
│       └── seccomp.json   # Linux syscall whitelist
├── install/
│   ├── install_linux_macos.sh
│   └── install_windows.ps1
└── requirements.txt
```

---

## 🤝 Pricing Tiers

| | Free | Paid |
|---|---|---|
| Earn DMC | ✓ | ✓ |
| Compute access | Own hardware only | Full network |
| Priority queue | — | ✓ |
| Advanced AI models | — | ✓ |
| Project investment | ✓ | ✓ |
| API access | — | ✓ |
| Payment | Free | DMC or Fiat |

---

## 🛡 Scripture Foundation

*"The grass withers, the flower fades, but the word of our God stands forever."* — Isaiah 40:8

*"Jesus said to him, 'I am the way, and the truth, and the life.'"* — John 14:6

*"Be strong and courageous. Do not be afraid; do not be discouraged, for the Lord your God will be with you wherever you go."* — Joshua 1:9

*"For I know the plans I have for you, declares the Lord, plans to prosper you and not to harm you, plans to give you hope and a future."* — Jeremiah 29:11

---

## 📜 License

MIT License — Free to use, fork, and build upon.

> *"Give, and it will be given to you."* — Luke 6:38

---

## 🤲 Contributing

Pull requests welcome. All contributors agree to our Code of Conduct grounded in:
*"Do to others as you would have them do to you."* — Luke 6:31

---

**DivineMesh Network** · Built on Faith, Secured by Cryptography, Powered by Community

*"Let your light shine before others."* — Matthew 5:16
