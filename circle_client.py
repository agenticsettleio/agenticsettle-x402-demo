"""
circle_client.py — shared helpers for calling Circle's Developer-Controlled
Wallets API from local scripts.

Reads CIRCLE_API_KEY from the environment and the raw entity secret from
./entity_secret.local.txt (created by generate_entity_secret.py). Neither
value is ever printed or sent anywhere except directly to Circle's API.

Circle requires a FRESH entitySecretCiphertext for every mutating API call
(RSA-OAEP encryption is non-deterministic, so re-encrypting the same raw
secret produces a different, single-use ciphertext each time) — this
module's `fresh_ciphertext()` does that on demand.
"""

from __future__ import annotations

import base64
import os
import sys

import httpx
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA

CIRCLE_API_BASE = "https://api.circle.com/v1/w3s"
SECRET_FILE = "entity_secret.local.txt"


def _api_key() -> str:
    api_key = os.environ.get("CIRCLE_API_KEY", "")
    if not api_key:
        print(
            'ERROR: CIRCLE_API_KEY is not set. Run: $env:CIRCLE_API_KEY = "..."',
            file=sys.stderr,
        )
        sys.exit(1)
    return api_key


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }


def fetch_public_key() -> str:
    resp = httpx.get(
        f"{CIRCLE_API_BASE}/config/entity/publicKey",
        headers=_headers(),
        timeout=30.0,
    )
    resp.raise_for_status()
    public_key_pem = resp.json().get("data", {}).get("publicKey")
    if not public_key_pem:
        print(f"ERROR: unexpected publicKey response: {resp.text}", file=sys.stderr)
        sys.exit(1)
    return public_key_pem


def fresh_ciphertext(public_key_pem: str) -> str:
    """Re-encrypt the locally-stored raw entity secret. Required fresh for
    every mutating Circle API call — never reuse a ciphertext across requests."""
    if not os.path.exists(SECRET_FILE):
        print(
            f"ERROR: {SECRET_FILE} not found. Run generate_entity_secret.py first.",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(SECRET_FILE, encoding="utf-8") as f:
        hex_secret = f.read().strip()
    entity_secret = bytes.fromhex(hex_secret)

    public_key = RSA.importKey(public_key_pem)
    cipher_rsa = PKCS1_OAEP.new(key=public_key, hashAlgo=SHA256)
    encrypted = cipher_rsa.encrypt(entity_secret)
    return base64.b64encode(encrypted).decode()


def post(path: str, body: dict) -> dict:
    resp = httpx.post(f"{CIRCLE_API_BASE}{path}", headers=_headers(), json=body, timeout=30.0)
    if resp.status_code >= 400:
        print(f"ERROR {resp.status_code} calling {path}: {resp.text}", file=sys.stderr)
        sys.exit(1)
    return resp.json()
