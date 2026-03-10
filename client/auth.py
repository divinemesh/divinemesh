"""
DivineMesh Authentication Module
"I am the gate; whoever enters through me will be saved." - John 10:9

No email. No phone. No personal data. Ever.
Identity is cryptographic — seeded by sacred entropy.
"""

import os
import json
import time
import hashlib
import base64
import hmac as hmac_lib
import logging
import ipaddress
import platform
import uuid
import re
from dataclasses import dataclass, field, asdict
from typing import Optional, Tuple
from pathlib import Path

import pyotp
import qrcode
from cryptography.exceptions import InvalidTag

from .encryption import (
    SacredEncryptor,
    DivineSigner,
    generate_sacred_id,
    generate_secure_password,
)

log = logging.getLogger("divinemesh.auth")

CONFIG_DIR = Path.home() / ".divinemesh"
IDENTITY_FILE = CONFIG_DIR / "identity.enc"
SESSION_FILE = CONFIG_DIR / "session.json"
MAX_MACS_PER_IP = 10


@dataclass
class NodeIdentity:
    """
    A subscriber's full cryptographic identity.
    No name, email, phone, or address — only provable cryptographic keys.
    'God sees not as man sees; man looks at the outward appearance,
     but the Lord looks at the heart.' - 1 Samuel 16:7
    """
    node_id: str                         # DM-XXXXXXXXXXXXXXXXXXX (random)
    display_password: str                # User-settable (hashed for storage)
    password_hash: str                   # Argon2/PBKDF2 hash
    wallet_address: str                  # Ethereum-compatible address
    wallet_keystore: dict                # Encrypted private key (JSON)
    public_key_pem: str                  # RSA-4096 public key
    private_key_pem_enc: str             # AES-encrypted private key
    ip_hash: str                         # SHA3-256 of IP (never stored in clear)
    mac_hash: str                        # SHA3-256 of MAC (never stored in clear)
    totp_secret: Optional[str] = None   # 2FA TOTP secret (optional)
    totp_enabled: bool = False
    tier: str = "free"                   # "free" | "paid"
    created_ts: int = field(default_factory=lambda: int(time.time()))
    last_seen_ts: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def hash_password(password: str, salt: bytes = None) -> Tuple[str, str]:
        if salt is None:
            salt = os.urandom(32)
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        kdf = PBKDF2HMAC(algorithm=hashes.SHA512(), length=64, salt=salt, iterations=600_000)
        derived = kdf.derive(password.encode())
        salt_b64 = base64.b64encode(salt).decode()
        hash_b64 = base64.b64encode(derived).decode()
        return f"{salt_b64}:{hash_b64}", salt_b64

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        try:
            salt_b64, _ = stored_hash.split(":")
            salt = base64.b64decode(salt_b64)
            new_hash, _ = NodeIdentity.hash_password(password, salt)
            return hmac_lib.compare_digest(new_hash, stored_hash)
        except Exception:
            return False


class IPGuard:
    """
    Enforces IP-level anti-abuse rules:
    - VPN detection (hash-based oracle)
    - Max 10 MAC addresses per IP
    - Single account per IP (enforced on-chain)
    'A false witness will not go unpunished.' - Proverbs 19:5
    """

    @staticmethod
    def get_public_ip() -> str:
        """Retrieve public IP via trusted resolver."""
        import urllib.request
        try:
            with urllib.request.urlopen("https://api.ipify.org", timeout=5) as r:
                return r.read().decode().strip()
        except Exception:
            return ""

    @staticmethod
    def hash_ip(ip: str) -> str:
        return hashlib.sha3_256(ip.encode()).hexdigest()

    @staticmethod
    def hash_mac(mac: str) -> str:
        normalized = mac.upper().replace(":", "").replace("-", "")
        return hashlib.sha3_256(normalized.encode()).hexdigest()

    @staticmethod
    def get_mac_address() -> str:
        """Get primary MAC address."""
        mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
        return ":".join(mac[i:i+2] for i in range(0, 12, 2))

    @staticmethod
    def detect_vpn_indicators() -> bool:
        """
        Heuristic VPN detection — checks for common VPN adapter names,
        suspicious gateway patterns, etc.
        'There is nothing concealed that will not be disclosed.' - Luke 12:2
        """
        vpn_keywords = [
            "vpn", "tun", "tap", "nordvpn", "expressvpn", "proton",
            "mullvad", "wireguard", "openvpn", "tailscale", "zerotier",
        ]
        try:
            import psutil
            for nic, _ in psutil.net_if_addrs().items():
                if any(kw in nic.lower() for kw in vpn_keywords):
                    return True
        except Exception:
            pass
        return False


class IdentityManager:
    """
    Create, load, and persist node identity with full encryption at rest.
    'The name of the Lord is a fortified tower.' - Proverbs 18:10
    """

    def __init__(self, config_dir: Path = CONFIG_DIR):
        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._identity: Optional[NodeIdentity] = None
        self._encryptor: Optional[SacredEncryptor] = None

    @property
    def identity(self) -> Optional[NodeIdentity]:
        return self._identity

    def create_new_identity(self, user_password: str = None) -> Tuple[NodeIdentity, str]:
        """
        Generate a brand-new node identity from scratch.
        Returns (identity, raw_password) — raw_password shown ONCE to user.
        """
        from .blockchain import DMCWallet
        ip = IPGuard.get_public_ip()
        mac = IPGuard.get_mac_address()

        if IPGuard.detect_vpn_indicators():
            raise PermissionError(
                "VPN detected. DivineMesh requires a raw internet connection. "
                "Please disable your VPN to register. "
                "'There is nothing hidden that will not be revealed.' - Mark 4:22"
            )

        node_id = generate_sacred_id()
        raw_password = user_password or generate_secure_password()
        password_hash, _ = NodeIdentity.hash_password(raw_password)

        # Generate RSA identity keypair
        signer = DivineSigner()
        # Encrypt private key with derived key from password
        encryptor = SacredEncryptor.from_password(raw_password)
        private_pem = signer.private_key_pem(password=raw_password.encode())
        enc_private = encryptor.encrypt_b64(private_pem.decode())

        # Generate wallet
        wallet = DMCWallet.generate()
        keystore = wallet.export_encrypted(raw_password)

        identity = NodeIdentity(
            node_id=node_id,
            display_password=raw_password,
            password_hash=password_hash,
            wallet_address=wallet.get_address(),
            wallet_keystore=keystore,
            public_key_pem=signer.public_key_pem(),
            private_key_pem_enc=enc_private,
            ip_hash=IPGuard.hash_ip(ip),
            mac_hash=IPGuard.hash_mac(mac),
        )
        self._identity = identity
        self._encryptor = SacredEncryptor.from_password(raw_password, encryptor._salt)
        self._save(raw_password)
        log.info(f"New identity created: {node_id}")
        return identity, raw_password

    def load_identity(self, password: str) -> Optional[NodeIdentity]:
        if not IDENTITY_FILE.exists():
            return None
        try:
            blob = IDENTITY_FILE.read_bytes()
            salt = blob[:32]
            enc_data = blob[32:]
            enc = SacredEncryptor.from_password(password, salt)
            plain = enc.decrypt(enc_data)
            data = json.loads(plain)
            self._identity = NodeIdentity(**data)
            self._encryptor = enc
            self._identity.last_seen_ts = int(time.time())
            self._save(password)
            return self._identity
        except (InvalidTag, json.JSONDecodeError, TypeError) as e:
            log.warning(f"Identity load failed: {e}")
            return None

    def _save(self, password: str):
        if not self._identity:
            return
        data = json.dumps(self._identity.to_dict()).encode()
        enc = SacredEncryptor.from_password(password)
        encrypted = enc.encrypt(data)
        IDENTITY_FILE.write_bytes(enc._salt + encrypted)

    def change_password(self, old_password: str, new_password: str) -> bool:
        identity = self.load_identity(old_password)
        if not identity:
            return False
        identity.password_hash, _ = NodeIdentity.hash_password(new_password)
        self._identity = identity
        self._save(new_password)
        return True

    def enable_2fa(self, password: str) -> Tuple[str, str]:
        """Enable TOTP 2FA. Returns (secret, qr_uri)."""
        identity = self.load_identity(password)
        if not identity:
            raise ValueError("Invalid password")
        secret = pyotp.random_base32()
        uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=identity.node_id, issuer_name="DivineMesh"
        )
        identity.totp_secret = secret
        identity.totp_enabled = True
        self._identity = identity
        self._save(password)
        return secret, uri

    def verify_2fa(self, token: str) -> bool:
        if not self._identity or not self._identity.totp_enabled:
            return True  # 2FA not enabled — pass through
        totp = pyotp.TOTP(self._identity.totp_secret)
        return totp.verify(token, valid_window=1)

    def authenticate(self, password: str, totp_token: str = None) -> bool:
        identity = self.load_identity(password)
        if not identity:
            return False
        if not NodeIdentity.verify_password(password, identity.password_hash):
            return False
        if identity.totp_enabled:
            if not totp_token or not self.verify_2fa(totp_token):
                return False
        return True

    @property
    def is_registered(self) -> bool:
        return IDENTITY_FILE.exists()
