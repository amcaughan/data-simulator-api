from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np


def derive_seed(seed: int | None, *parts: Any) -> int | None:
    if seed is None:
        return None

    payload = json.dumps([seed, *parts], separators=(",", ":"), default=str)
    digest = hashlib.blake2b(payload.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)


def build_rng(seed: int | None, *parts: Any) -> np.random.Generator:
    return np.random.default_rng(derive_seed(seed, *parts))
