"""
DivineMesh Blockchain Module
"Do not store up for yourselves treasures on earth... but store up for yourselves
 treasures in heaven." - Matthew 6:19-20

DivineMesh uses a hybrid approach:
  - On-chain: Ethereum-compatible (EVM) for DMC token, user registry, project shares
  - Off-chain: Merkle-tree verified compute proofs anchored on-chain
"""

import json
import hashlib
import time
import os
import secrets
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
from decimal import Decimal

from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account
from eth_account.messages import encode_defunct

log = logging.getLogger("divinemesh.blockchain")

# ── Network Configuration ─────────────────────────────────────────────────────
NETWORKS = {
    "mainnet": {
        "rpc": "https://mainnet.infura.io/v3/{INFURA_KEY}",
        "chain_id": 1,
        "explorer": "https://etherscan.io",
    },
    "polygon": {
        "rpc": "https://polygon-rpc.com",
        "chain_id": 137,
        "explorer": "https://polygonscan.com",
    },
    "bsc": {
        "rpc": "https://bsc-dataseed.binance.org/",
        "chain_id": 56,
        "explorer": "https://bscscan.com",
    },
    "testnet": {
        "rpc": "https://sepolia.infura.io/v3/{INFURA_KEY}",
        "chain_id": 11155111,
        "explorer": "https://sepolia.etherscan.io",
    },
}

# DivineMesh Coin (DMC) token contract ABI (ERC-20 + custom staking)
DMC_ABI = json.loads("""
[
  {"inputs":[],"name":"name","outputs":[{"type":"string"}],"stateMutability":"view","type":"function"},
  {"inputs":[],"name":"symbol","outputs":[{"type":"string"}],"stateMutability":"view","type":"function"},
  {"inputs":[],"name":"decimals","outputs":[{"type":"uint8"}],"stateMutability":"view","type":"function"},
  {"inputs":[],"name":"totalSupply","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"type":"bool"}],"stateMutability":"nonpayable","type":"function"},
  {"inputs":[{"name":"nodeId","type":"bytes32"},{"name":"computeUnits","type":"uint256"},{"name":"proof","type":"bytes32"}],"name":"claimReward","outputs":[],"stateMutability":"nonpayable","type":"function"},
  {"inputs":[{"name":"nodeId","type":"bytes32"}],"name":"getNodeBalance","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"name":"projectId","type":"bytes32"},{"name":"amount","type":"uint256"}],"name":"investInProject","outputs":[],"stateMutability":"nonpayable","type":"function"},
  {"inputs":[{"name":"projectId","type":"bytes32"},{"name":"investor","type":"address"}],"name":"getProjectShare","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"}
]
""")

# User Registry ABI — no personal info stored, only hash of node ID + public key
REGISTRY_ABI = json.loads("""
[
  {"inputs":[{"name":"nodeId","type":"bytes32"},{"name":"pubKeyHash","type":"bytes32"},{"name":"ipHash","type":"bytes32"}],"name":"registerNode","outputs":[],"stateMutability":"nonpayable","type":"function"},
  {"inputs":[{"name":"nodeId","type":"bytes32"}],"name":"isRegistered","outputs":[{"type":"bool"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"name":"ipHash","type":"bytes32"}],"name":"getMacCount","outputs":[{"type":"uint8"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"name":"nodeId","type":"bytes32"},{"name":"macHash","type":"bytes32"}],"name":"registerMac","outputs":[{"type":"bool"}],"stateMutability":"nonpayable","type":"function"}
]
""")


@dataclass
class ComputeProof:
    """
    Proof-of-Work record for completed compute tasks.
    'Whatever you do, work at it with all your heart.' - Colossians 3:23
    """
    task_id: str
    node_id: str
    cpu_seconds: float
    gpu_seconds: float
    ram_gb_hours: float
    start_ts: int
    end_ts: int
    result_hash: str
    merkle_root: str = ""
    signature: str = ""

    def compute_units(self) -> float:
        """DMC reward formula: CPU + 4×GPU + 0.5×RAM"""
        return self.cpu_seconds + 4 * self.gpu_seconds + 0.5 * self.ram_gb_hours

    def to_hash(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True).encode()
        return hashlib.sha3_256(payload).hexdigest()


@dataclass
class ProjectListing:
    """
    A user-posted compute project open for investor compute-power donations.
    'Plans are established by seeking advice.' - Proverbs 20:18
    """
    project_id: str
    title: str
    description: str
    owner_node_id: str
    required_compute_units: float
    current_compute_units: float = 0.0
    owner_share_pct: float = 51.0          # Owner always holds ≥51%
    investor_pool_pct: float = 49.0
    investors: Dict[str, float] = field(default_factory=dict)
    is_active: bool = True
    created_ts: int = field(default_factory=lambda: int(time.time()))
    signed_agreements: List[str] = field(default_factory=list)

    def add_compute_donation(self, node_id: str, units: float):
        total = self.current_compute_units + units
        if total == 0:
            return
        # Rebalance investor shares proportionally
        old_share = self.investors.get(node_id, 0.0)
        new_share = (old_share + units) / (self.current_compute_units + units) * self.investor_pool_pct
        # Scale others
        scale = (self.investor_pool_pct - new_share) / max(self.investor_pool_pct - old_share * self.investor_pool_pct / 100, 0.001)
        for nid in self.investors:
            if nid != node_id:
                self.investors[nid] *= scale
        self.investors[node_id] = new_share
        self.current_compute_units = total


class DMCWallet:
    """
    DivineMesh Coin wallet — wraps an Ethereum-compatible EOA.
    Stores private key encrypted with user's sacred password.
    'The Lord is my strength and my shield.' - Psalm 28:7
    """

    def __init__(self, private_key: str = None):
        if private_key:
            self.account = Account.from_key(private_key)
        else:
            self.account = Account.create(extra_entropy=os.urandom(32).hex())
        self.address = self.account.address

    @classmethod
    def generate(cls) -> "DMCWallet":
        return cls()

    def sign_message(self, message: str) -> str:
        msg = encode_defunct(text=message)
        signed = self.account.sign_message(msg)
        return signed.signature.hex()

    def export_encrypted(self, password: str) -> dict:
        return Account.encrypt(self.account.key, password)

    @classmethod
    def from_encrypted(cls, keystore: dict, password: str) -> "DMCWallet":
        pk = Account.decrypt(keystore, password)
        return cls(pk.hex())

    def get_address(self) -> str:
        return self.address


class BlockchainClient:
    """
    Connects to EVM network, interacts with DMC token + registry contracts.
    'Let all things be done decently and in order.' - 1 Corinthians 14:40
    """

    def __init__(
        self,
        network: str = "polygon",
        dmc_contract_address: str = None,
        registry_contract_address: str = None,
        infura_key: str = None,
    ):
        cfg = NETWORKS[network]
        rpc = cfg["rpc"].replace("{INFURA_KEY}", infura_key or "")
        self.w3 = Web3(Web3.HTTPProvider(rpc))
        if network in ("polygon", "bsc"):
            self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        self.chain_id = cfg["chain_id"]
        self.explorer = cfg["explorer"]

        if dmc_contract_address:
            self.dmc = self.w3.eth.contract(
                address=Web3.to_checksum_address(dmc_contract_address),
                abi=DMC_ABI,
            )
        else:
            self.dmc = None

        if registry_contract_address:
            self.registry = self.w3.eth.contract(
                address=Web3.to_checksum_address(registry_contract_address),
                abi=REGISTRY_ABI,
            )
        else:
            self.registry = None

    def is_connected(self) -> bool:
        return self.w3.is_connected()

    def get_dmc_balance(self, address: str) -> Decimal:
        if not self.dmc:
            return Decimal(0)
        raw = self.dmc.functions.balanceOf(Web3.to_checksum_address(address)).call()
        return Decimal(raw) / Decimal(10 ** 18)

    def claim_reward(self, wallet: DMCWallet, proof: ComputeProof) -> str:
        """Submit compute proof on-chain and claim DMC reward."""
        if not self.dmc:
            raise RuntimeError("DMC contract not configured")
        nonce = self.w3.eth.get_transaction_count(wallet.address)
        node_id_bytes = hashlib.sha3_256(proof.node_id.encode()).digest()
        result_bytes = bytes.fromhex(proof.result_hash[:64].ljust(64, "0"))
        units_wei = int(proof.compute_units() * 10 ** 18)
        tx = self.dmc.functions.claimReward(
            node_id_bytes, units_wei, result_bytes
        ).build_transaction(
            {
                "chainId": self.chain_id,
                "gas": 200_000,
                "gasPrice": self.w3.eth.gas_price,
                "nonce": nonce,
            }
        )
        signed = self.w3.eth.account.sign_transaction(tx, wallet.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        return tx_hash.hex()

    def register_node(self, wallet: DMCWallet, node_id: str, pub_key_pem: str, ip_hash: str) -> str:
        if not self.registry:
            raise RuntimeError("Registry contract not configured")
        nid = hashlib.sha3_256(node_id.encode()).digest()
        pkh = hashlib.sha3_256(pub_key_pem.encode()).digest()
        iph = bytes.fromhex(ip_hash[:64].ljust(64, "0"))
        nonce = self.w3.eth.get_transaction_count(wallet.address)
        tx = self.registry.functions.registerNode(nid, pkh, iph).build_transaction(
            {
                "chainId": self.chain_id,
                "gas": 150_000,
                "gasPrice": self.w3.eth.gas_price,
                "nonce": nonce,
            }
        )
        signed = self.w3.eth.account.sign_transaction(tx, wallet.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        return tx_hash.hex()

    def is_vpn_ip(self, ip: str) -> bool:
        """
        Check if IP is a known VPN/proxy endpoint.
        Uses on-chain VPN blacklist oracle (updated weekly by governance).
        """
        ip_hash = hashlib.sha3_256(ip.encode()).hexdigest()
        # TODO: query on-chain VPN oracle contract
        return False

    def get_mac_count_for_ip(self, ip_hash: str) -> int:
        """Max 10 MAC addresses per IP to prevent monetization abuse."""
        if not self.registry:
            return 0
        iph = bytes.fromhex(ip_hash[:64].ljust(64, "0"))
        return self.registry.functions.getMacCount(iph).call()


class MerkleTree:
    """
    Compute task Merkle tree for batch proof anchoring.
    'Every good tree bears good fruit.' - Matthew 7:17
    """

    def __init__(self, leaves: List[bytes]):
        self.leaves = [hashlib.sha3_256(leaf).digest() for leaf in leaves]
        self.tree = self._build()

    def _build(self) -> List[List[bytes]]:
        level = list(self.leaves)
        tree = [level]
        while len(level) > 1:
            if len(level) % 2 == 1:
                level.append(level[-1])
            level = [
                hashlib.sha3_256(level[i] + level[i + 1]).digest()
                for i in range(0, len(level), 2)
            ]
            tree.append(level)
        return tree

    @property
    def root(self) -> str:
        return self.tree[-1][0].hex() if self.tree and self.tree[-1] else ""

    def proof(self, index: int) -> List[str]:
        proof_path = []
        for level in self.tree[:-1]:
            if len(level) % 2 == 1:
                level = level + [level[-1]]
            sibling = index ^ 1
            if sibling < len(level):
                proof_path.append(level[sibling].hex())
            index //= 2
        return proof_path


# ── Profit Distribution ───────────────────────────────────────────────────────
# 'Honor the Lord with your wealth.' - Proverbs 3:9
PROFIT_ACCOUNTS = {
    "primary":    {"share": 0.50, "label": "Primary Operations"},
    "reserve":    {"share": 0.30, "label": "Reserve & Development"},
    "tithe":      {"share": 0.20, "label": "Community & Charity"},
}

def distribute_profit(total_dmc: float) -> Dict[str, float]:
    """Split platform profit into three owner-controlled accounts."""
    return {key: total_dmc * val["share"] for key, val in PROFIT_ACCOUNTS.items()}
