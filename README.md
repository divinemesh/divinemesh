# ✝️ DivineMesh Network

> *"For where two or three gather in my name, there am I with them."* — Matthew 18:20

**DivineMesh** is a decentralized, privacy-first distributed computing network that rewards contributors with **DMC (DivineMesh Coin)** for sharing their computer's processing power.

---

## 🌐 Links

| | |
|---|---|
| 🌍 **Website** | https://divinemesh.com |
| 🏫 **Coordinator** | https://coordinator.divinemesh.com |
| 📊 **Network Stats** | https://coordinator.divinemesh.com/api/v1/stats |
| 🏆 **Leaderboard** | https://coordinator.divinemesh.com/api/v1/leaderboard |
| 👥 **Live Nodes** | https://coordinator.divinemesh.com/api/v1/nodes |

---

## ⚡ Quick Install

### Linux / macOS
```bash
curl -sSL https://divinemesh.com/install.sh | bash
```

### Windows (PowerShell — run as Administrator)
```powershell
irm https://divinemesh.com/install.ps1 | iex
```

### Android (Termux)
```bash
curl -sSL https://divinemesh.com/install-android.sh | bash
```

### Docker
```bash
git clone https://github.com/divinemesh/divinemesh.git
cd divinemesh
docker compose up -d
```

---

## 💰 How Earning Works

When your node completes compute tasks, you earn **DMC coins** automatically:

| Resource | Reward Rate |
|---|---|
| CPU time | 0.001 DMC per second |
| GPU time | 0.004 DMC per second |
| RAM (per GB/hr) | 0.0005 DMC |

DMC is an ERC-20 token on the **Polygon** network. Low gas fees, fast transactions.

**Profit split (per proof):**
- 50% to Primary owner wallet
- 30% to Secondary owner wallet
- 20% to Development wallet

---

## 🔒 Privacy and Security

- **Zero PII collected** — only SHA3-256 hashes stored on-chain
- **AES-256-GCM** encryption for all data at rest
- **RSA-4096** for key exchange
- **PBKDF2-SHA512** with Biblical entropy for key derivation
- No IP addresses stored — ever
- Sandboxed task execution — tasks cannot access your files

Your Node ID looks like: `DM-XXXXXXXXXXXXXXXXXXXXXXXXXX`
No name, no email, no location — just a random sacred ID.

---

## Architecture

```
                    INTERNET
                         |
              coordinator.divinemesh.com
                   (The Teacher)
               /          |          \
        Your Node      Node 2      Node 3
        (earning DMC)  (Tokyo)    (Brazil)
```

### Components

| File | Purpose |
|---|---|
| `client/daemon.py` | Main node daemon, REST API on port 7474 |
| `client/auth.py` | Zero-PII identity management |
| `client/encryption.py` | AES-256-GCM + RSA-4096 encryption |
| `client/blockchain.py` | Polygon/EVM wallet + proof submission |
| `client/hardware_monitor.py` | CPU/GPU/RAM monitoring + task sandbox |
| `client/worker.py` | Isolated task execution subprocess |
| `coordinator/coordinator.py` | Network coordinator server |
| `contracts/DivineMesh.sol` | DMC ERC-20 smart contract |
| `dashboard/index.html` | Web dashboard |

---

## Docker Deployment

```bash
git clone https://github.com/divinemesh/divinemesh.git
cd divinemesh
docker compose up -d
docker compose ps
docker compose logs -f divinemesh-node
```

---

## Requirements

| Platform | Requirements |
|---|---|
| Linux | Python 3.10+, 512MB RAM, 1GB disk |
| macOS | Python 3.10+, 512MB RAM, 1GB disk |
| Windows | Python 3.10+, PowerShell 5+, 512MB RAM |
| Android | Termux, Python 3.10+, 256MB RAM |
| Docker | Docker 24+, Docker Compose v2 |

---

## DMC Token

- **Name:** DivineMesh Coin
- **Symbol:** DMC
- **Network:** Polygon (EVM)
- **Max Supply:** 144,000,000 *(Revelation 7:4)*
- **Contract:** deploy via `contracts/DivineMesh.sol`

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit: `git commit -m "Add my feature"`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

---

## License

MIT License — free to use, modify, and distribute.

---

> *"Give, and it will be given to you."* — Luke 6:38

**DivineMesh** — Compute for the Kingdom. Pray. Build. Earn. 🙏
