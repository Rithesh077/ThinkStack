"""
key derivation module.

turns a human password into a 256-bit aes key using argon2id.
the same password always produces a different key per paper because
each paper gets its own random salt.
"""

import os
from dataclasses import dataclass

from argon2.low_level import Type, hash_secret_raw

# tunable cost parameters. these are deliberately expensive: the goal
# is ~0.3-0.6 seconds on typical hardware. raise memory_cost_kib first
# if you want it slower -- that's the knob that hurts gpu attackers most.
TIME_COST = 3
MEMORY_COST_KIB = 65536  # 64 MiB
PARALLELISM = 4
KEY_LENGTH_BYTES = 32  # 256 bits, required by aes-256
SALT_LENGTH_BYTES = 16


@dataclass(frozen=True)
class KdfParams:
    """the cost parameters used for one specific key derivation.

    stored alongside the ciphertext (not secret) so that decryption
    later uses the *exact* same settings the key was derived with.
    if you tune the constants above for new papers, old papers still
    decrypt correctly because their own params travel with them.
    """
    time_cost: int
    memory_cost_kib: int
    parallelism: int

    @classmethod
    def current_defaults(cls) -> "KdfParams":
        return cls(
            time_cost=TIME_COST,
            memory_cost_kib=MEMORY_COST_KIB,
            parallelism=PARALLELISM,
        )


def generate_salt() -> bytes:
    """generate a fresh cryptographically random salt.

    uses os.urandom, which reads from the operating system's secure
    random source -- never use python's `random` module for anything
    security-related, it is not designed to be unpredictable.
    """
    return os.urandom(SALT_LENGTH_BYTES)


def derive_key(password: str, salt: bytes, params: KdfParams) -> bytes:
    """derive a 256-bit key from a password and salt using argon2id.

    args:
        password: the user's plaintext password. never stored, never
            logged, used here and then discarded by the caller.
        salt: random bytes unique to this paper. not secret.
        params: cost parameters to use for this derivation.

    returns:
        32 raw bytes suitable for use as an aes-256 key.
    """
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=params.time_cost,
        memory_cost=params.memory_cost_kib,
        parallelism=params.parallelism,
        hash_len=KEY_LENGTH_BYTES,
        type=Type.ID,  # this is what selects argon2id over argon2i/argon2d
    )
