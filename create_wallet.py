"""
create_wallet.py — create a Base Sepolia developer-controlled wallet via
Circle's API, to use as the X402_PAY_TO_ADDRESS for x402_verify_gateway.py.

Run locally:
    $env:CIRCLE_API_KEY = "..."   (same key used for generate_entity_secret.py)
    python create_wallet.py

Prints only the wallet set id and wallet address (both safe to share/paste
into chat) — no secrets are printed.
"""

from __future__ import annotations

import sys
import uuid

from circle_client import fetch_public_key, fresh_ciphertext, post


def main() -> None:
    public_key_pem = fetch_public_key()

    # Step 1 — create a wallet set (a container for one or more wallets).
    wallet_set_resp = post(
        "/developer/walletSets",
        {
            "idempotencyKey": str(uuid.uuid4()),
            "name": "agenticsettle-x402-demo",
            "entitySecretCiphertext": fresh_ciphertext(public_key_pem),
        },
    )
    wallet_set_id = wallet_set_resp.get("data", {}).get("walletSet", {}).get("id")
    if not wallet_set_id:
        print(f"ERROR: unexpected walletSets response: {wallet_set_resp}", file=sys.stderr)
        sys.exit(1)
    print(f"Wallet set created: {wallet_set_id}")

    # Step 2 — create one EOA wallet on Base Sepolia within that set.
    # Note: entitySecretCiphertext must be freshly generated again here —
    # Circle rejects a ciphertext that was already used in a prior request.
    wallet_resp = post(
        "/developer/wallets",
        {
            "idempotencyKey": str(uuid.uuid4()),
            "entitySecretCiphertext": fresh_ciphertext(public_key_pem),
            "walletSetId": wallet_set_id,
            "blockchains": ["BASE-SEPOLIA"],
            "accountType": "EOA",
            "count": 1,
        },
    )
    wallets = wallet_resp.get("data", {}).get("wallets", [])
    if not wallets:
        print(f"ERROR: unexpected wallets response: {wallet_resp}", file=sys.stderr)
        sys.exit(1)

    wallet = wallets[0]
    print()
    print("Wallet created:")
    print(f"  id:      {wallet.get('id')}")
    print(f"  address: {wallet.get('address')}")
    print(f"  chain:   {wallet.get('blockchain')}")
    print()
    print("Set this as X402_PAY_TO_ADDRESS:")
    print(f'  $env:X402_PAY_TO_ADDRESS = "{wallet.get("address")}"')


if __name__ == "__main__":
    main()
