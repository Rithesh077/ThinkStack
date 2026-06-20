"""
cipher module.

wraps aes-256-gcm authenticated encryption. encrypting also produces
an authentication tag; decrypting with the wrong key makes that tag
check fail loudly instead of returning corrupted plaintext.
"""

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_LENGTH_BYTES = 12


class DecryptionError(Exception):
    """raised when decryption fails: wrong password, corrupted data,
    or tampered ciphertext. deliberately doesn't distinguish which --
    telling an attacker *why* it failed leaks information.
    """


def generate_nonce() -> bytes:
    """generate a fresh random nonce. must never be reused with the
    same key -- generating it fresh every call is what guarantees that.
    """
    return os.urandom(NONCE_LENGTH_BYTES)


def encrypt(key: bytes, nonce: bytes, plaintext: bytes) -> bytes:
    """encrypt plaintext with aes-256-gcm.

    args:
        key: 32-byte key, e.g. from kdf.derive_key.
        nonce: 12-byte nonce, e.g. from generate_nonce. must be unique
            per (key, nonce) pair -- never reused.
        plaintext: the raw bytes to encrypt.

    returns:
        ciphertext with the 16-byte auth tag appended at the end
        (this is the standard layout AESGCM produces).
    """
    aesgcm = AESGCM(key)
    return aesgcm.encrypt(nonce, plaintext, associated_data=None)


def decrypt(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    """decrypt ciphertext produced by encrypt().

    args:
        key: the 32-byte key. must be the exact key used to encrypt --
            in this system that means the password and salt must match.
        nonce: the same nonce used during encryption.
        ciphertext: bytes including the trailing 16-byte auth tag.

    returns:
        the original plaintext bytes.

    raises:
        DecryptionError: if the key is wrong or the ciphertext was
            tampered with / corrupted.
    """
    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(nonce, ciphertext, associated_data=None)
    except InvalidTag as exc:
        raise DecryptionError(
            "decryption failed: wrong password or corrupted data"
        ) from exc
