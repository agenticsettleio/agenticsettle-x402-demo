"""
test_payment.py — end-to-end x402 payment test against a locally-running
x402_verify_gateway.py.

Prerequisites:
  1. x402_verify_gateway.py already running (uvicorn x402_verify_gateway:app --port 4021)
  2. generate_test_payer.py already run, and the printed address funded
     with testnet USDC on Base Sepolia via https://faucet.circle.com

Run:
    pip install "x402[httpx]" eth-account
    python test_payment.py

Uses the local test payer's private key (never printed) to actually sign
and submit an x402 payment, then prints the VOP verification result
returned by the (now successfully paid) /verify call.
"""

from __future__ import annotations

import asyncio
import os
import sys

from eth_account import Account
from x402 import SchemeRegistration, x402Client, x402ClientConfig
from x402.http.clients import wrapHttpxWithPayment
from x402.mechanisms.evm.exact import ExactEvmScheme

KEY_FILE = "test_payer.local.txt"
GATEWAY_URL = os.getenv("X402_GATEWAY_URL", "http://127.0.0.1:4021")
NETWORK = os.getenv("X402_NETWORK", "eip155:84532")  # Base Sepolia


async def main() -> None:
    if not os.path.exists(KEY_FILE):
        print(
            f"ERROR: {KEY_FILE} not found. Run generate_test_payer.py first, "
            "then fund the printed address via https://faucet.circle.com",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(KEY_FILE, encoding="utf-8") as f:
        private_key = f.read().strip()
    account = Account.from_key(private_key)
    print(f"Paying from: {account.address}")

    config = x402ClientConfig(
        schemes=[SchemeRegistration(network=NETWORK, client=ExactEvmScheme(signer=account))],
    )
    client = x402Client.from_config(config)

    payload = {
        "request_content": "Summarize photosynthesis in one paragraph.",
        "result_content": (
            "Photosynthesis is the process by which plants convert light "
            "energy into chemical energy."
        ),
    }

    async with wrapHttpxWithPayment(client, timeout=60.0) as http:
        response = await http.post(f"{GATEWAY_URL}/verify", json=payload)

    print(f"Final status: {response.status_code}")
    print(response.text)


if __name__ == "__main__":
    asyncio.run(main())
