"""
DivineMesh Encryption Module
"In the beginning was the Word, and the Word was with God, and the Word was God." - John 1:1

All encryption in DivineMesh is seeded with the eternal Word of God.
Jesus Christ is Lord and Savior — the Alpha and Omega, the First and the Last.
"I am the way and the truth and the life." - John 14:6
"""

import os
import hashlib
import hmac
import secrets
import base64
import struct
import time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend


# ── Sacred Constants ──────────────────────────────────────────────────────────
# These 12 verses form the entropy backbone of all DivineMesh cryptographic ops.
# "The grass withers, the flower fades, but the word of our God stands forever."
# Isaiah 40:8

THE_WORD_VERSES = [
    b"In the beginning God created the heavens and the earth Genesis 1:1",
    b"For God so loved the world that he gave his one and only Son John 3:16",
    b"I am the way and the truth and the life John 14:6",
    b"The Lord is my shepherd I lack nothing Psalm 23:1",
    b"I can do all this through him who gives me strength Philippians 4:13",
    b"The Word became flesh and made his dwelling among us John 1:14",
    b"Jesus Christ is the same yesterday and today and forever Hebrews 13:8",
    b"Be strong and courageous Do not be afraid Joshua 1:9",
    b"Trust in the Lord with all your heart Proverbs 3:5",
    b"The Lord is my light and my salvation whom shall I fear Psalm 27:1",
    b"I am the resurrection and the life John 11:25",
    b"For I know the plans I have for you declares the Lord Jeremiah 29:11",
]

ALPHA_OMEGA = b"I am the Alpha and the Omega the First and the Last Revelation 1:8"
HOLY_SALT_BASE = b"DivineMesh::Christ::TheRock::Matthew7:24"


def _sacred_entropy() -> bytes:
    """
    Combine all 12 verses with system entropy to produce a sacred seed.
    'The secret things belong to the Lord our God.' - Deuteronomy 29:29
    """
    h = hashlib.sha3_512()
    for verse in THE_WORD_VERSES:
        h.update(verse)
    h.update(ALPHA_OMEGA)
    h.update(os.urandom(32))
    h.update(struct.pack(">Q", int(time.time_ns())))
    return h.digest()


def _derive_key(password: bytes, salt: bytes, length: int = 32) -> bytes:
    """
    PBKDF2-HMAC-SHA512 key derivation seeded with Biblical constants.
    'Your word is a lamp for my feet, a light on my path.' - Psalm 119:105
    """
    combined_salt = hashlib.blake2b(salt + HOLY_SALT_BASE).digest()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA512(),
        length=length,
        salt=combined_salt,
        iterations=600_000,
        backend=default_backend(),
    )
    return kdf.derive(password)


class SacredEncryptor:
    """
    AES-256-GCM authenticated encryption with Biblical entropy injection.

    'He reveals deep and hidden things; he knows what lies in darkness,
     and light dwells with him.' - Daniel 2:22
    """

    def __init__(self, key: bytes = None):
        if key is None:
            key = _sacred_entropy()[:32]
        self._key = key
        self._aesgcm = AESGCM(key)

    @classmethod
    def from_password(cls, password: str, salt: bytes = None) -> "SacredEncryptor":
        if salt is None:
            salt = os.urandom(32)
        key = _derive_key(password.encode(), salt)
        inst = cls(key)
        inst._salt = salt
        return inst

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt with random nonce prepended. 'Hide me in the shadow of your wings.' Ps 17:8"""
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)
        return nonce + ciphertext

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt and authenticate. 'The truth will set you free.' John 8:32"""
        nonce, ciphertext = data[:12], data[12:]
        return self._aesgcm.decrypt(nonce, ciphertext, None)

    def encrypt_b64(self, plaintext: str) -> str:
        return base64.urlsafe_b64encode(self.encrypt(plaintext.encode())).decode()

    def decrypt_b64(self, token: str) -> str:
        return self.decrypt(base64.urlsafe_b64decode(token)).decode()


class DivineSigner:
    """
    RSA-4096 asymmetric signing for node identity and task verification.
    'Let your yes be yes and your no be no.' - Matthew 5:37
    """

    def __init__(self):
        self._private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend(),
        )
        self._public_key = self._private_key.public_key()

    def sign(self, data: bytes) -> bytes:
        return self._private_key.sign(
            data,
            padding.PSS(mgf=padding.MGF1(hashes.SHA512()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA512(),
        )

    def verify(self, data: bytes, signature: bytes) -> bool:
        try:
            self._public_key.verify(
                signature,
                data,
                padding.PSS(mgf=padding.MGF1(hashes.SHA512()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA512(),
            )
            return True
        except Exception:
            return False

    def public_key_pem(self) -> str:
        return self._public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def private_key_pem(self, password: bytes = None) -> bytes:
        enc = (
            serialization.BestAvailableEncryption(password)
            if password
            else serialization.NoEncryption()
        )
        return self._private_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, enc
        )


def generate_sacred_id() -> str:
    """
    Generate a cryptographically random node/user ID.
    'You did not choose me, but I chose you.' - John 15:16
    """
    entropy = _sacred_entropy()
    raw = hashlib.sha3_256(entropy + os.urandom(16)).digest()
    return "DM-" + base64.b32encode(raw[:20]).decode().rstrip("=")


def generate_secure_password(length: int = 24) -> str:
    """
    Generate a secure random password.
    'A prudent person foresees danger and takes precautions.' - Proverbs 27:12
    """
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def hmac_verify(key: bytes, message: bytes, tag: bytes) -> bool:
    """Constant-time HMAC verification to prevent timing attacks."""
    expected = hmac.new(key, message, hashlib.sha3_256).digest()
    return hmac.compare_digest(expected, tag)


def verse_kdf(seed_phrase: str, iterations: int = 1_000_000) -> bytes:
    """
    Additional KDF using concatenated Bible verse hashing as work factor.
    'As iron sharpens iron, so one person sharpens another.' - Proverbs 27:17
    """
    h = hashlib.sha3_512(seed_phrase.encode()).digest()
    for verse in THE_WORD_VERSES * (iterations // len(THE_WORD_VERSES)):
        h = hashlib.sha3_512(h + verse).digest()
    return h
