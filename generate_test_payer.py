"""
generate_test_payer.py — create a local test wallet to act as the paying
x402 client, for end-to-end testing of x402_verify_gateway.py.

This is a throwaway TESTNET-only wallet, not a Circle-managed wallet.
The private key is written to a local file only and never printed to
the terminal or shared anywhere — only the public address is printed
(safe to share; it's what you fund via a faucet and nothing else).

Run:
    python generate_test_payer.py

Then fund the printed address with testnet USDC on Base Sepolia via
https://faucet.circle.com (select Base Sepolia + USDC).
"""

from __future__ import annotations

import os

from eth_account import Account

KEY_FILE = "test_payer.local.txt"


def main() -> None:
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, encoding="utf-8") as f:
            private_key = f.read().strip()
        account = Account.from_key(private_key)
        print(f"Reusing existing test payer wallet: {account.address}")
        return

    account = Account.create()
    with open(KEY_FILE, "w", encoding="utf-8") as f:
        f.write(account.key.hex())

    print(f"Test payer wallet created: {account.address}")
    print(f"Private key written to ./{KEY_FILE} (local only, gitignored).")
    print()
    print("Fund this address with testnet USDC on Base Sepolia:")
    print("  https://faucet.circle.com  (select Base Sepolia + USDC)")


if __name__ == "__main__":
    main()
