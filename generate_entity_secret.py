"""
generate_entity_secret.py — Circle developer-controlled wallet entity secret
==============================================================================

Run this LOCALLY. It never prints the raw entity secret or your API key to
a shared/logged location — the secret goes only to a local file, and the
API key is read from an environment variable you set yourself.

Steps:
1. In Circle Console, go to "Keys" and create an API key if you haven't yet.
2. Set it locally (do not paste it into a chat):
       export CIRCLE_API_KEY="your-key-here"
3. Run:  python generate_entity_secret.py
   This fetches your entity's public key from Circle's API
   (GET /config/entity/publicKey) automatically, then generates and
   encrypts a fresh entity secret with it.
4. The script prints ONLY the ciphertext — paste that into the Circle
   Console "Entity Secret Ciphertext" field and click Register.
5. The RAW entity secret is written to `entity_secret.local.txt`
   (already in .gitignore — never commit it, never paste it anywhere,
   including into a chat with an AI assistant). Back this file up
   somewhere safe (password manager, offline). Circle does not store it;
   if you lose it, you lose the ability to sign with wallets created
   under this entity.
6. When Circle Console offers the one-time recovery file download after
   you click Register, save that too, immediately — it cannot be
   re-downloaded later.
"""

import base64
import codecs
import os
import sys

import httpx
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA

CIRCLE_API_BASE = "https://api.circle.com/v1/w3s"
SECRET_OUTPUT_FILE = "entity_secret.local.txt"


def fetch_public_key(api_key: str) -> str:
    """Fetch this entity's RSA public key from Circle's API."""
    resp = httpx.get(
        f"{CIRCLE_API_BASE}/config/entity/publicKey",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    # Circle wraps the key under data.publicKey per the W3S API convention.
    public_key_pem = data.get("data", {}).get("publicKey")
    if not public_key_pem:
        print(f"ERROR: unexpected response shape: {data}", file=sys.stderr)
        sys.exit(1)
    return public_key_pem


def main() -> None:
    api_key = os.environ.get("CIRCLE_API_KEY", "")
    if not api_key:
        print(
            "ERROR: CIRCLE_API_KEY is not set.\n"
            "Get one from Circle Console -> Keys, then:\n"
            '    export CIRCLE_API_KEY="your-key-here"',
            file=sys.stderr,
        )
        sys.exit(1)

    public_key_string = fetch_public_key(api_key)

    # Step 1: generate a fresh 32-byte entity secret.
    entity_secret = os.urandom(32)
    hex_secret = codecs.encode(entity_secret, "hex").decode()

    # Step 2: encrypt with Circle's public key (RSA-OAEP, SHA-256) — matches
    # Circle's official sample code exactly (circlefin/w3s-entity-secret-sample-code).
    public_key = RSA.importKey(public_key_string)
    cipher_rsa = PKCS1_OAEP.new(key=public_key, hashAlgo=SHA256)
    encrypted_data = cipher_rsa.encrypt(entity_secret)
    ciphertext = base64.b64encode(encrypted_data).decode()

    # Step 3: save the raw secret locally ONLY — never print it to a shared terminal/log.
    with open(SECRET_OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(hex_secret + "\n")

    print(f"Raw entity secret written to ./{SECRET_OUTPUT_FILE} (keep this offline & backed up).")
    print("Do NOT paste that file's contents anywhere, including into a chat.")
    print()
    print("Paste this into the Circle Console 'Entity Secret Ciphertext' field:")
    print()
    print(ciphertext)


if __name__ == "__main__":
    main()
