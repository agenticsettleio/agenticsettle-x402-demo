# AgenticSettle × x402

A reference integration showing an AI agent paying per-call in USDC — via
the [x402 protocol](https://github.com/coinbase/x402) — to access
[AgenticSettle](https://agenticsettle.io) VOP output verification.

AgenticSettle verifies AI agent work product (does the output actually
meet the agreed criteria?) and conditionally settles payment based on the
result. This demo shows that verification call itself being paid for
autonomously by an agent over x402, with no API key provisioning step and
no human in the loop for the payment.

## What's here

- `x402_verify_gateway.py` — a standalone FastAPI server. It does not
  replace or modify AgenticSettle's backend; it's a thin paywall in front
  of the existing `POST /v2/verify` REST endpoint.
  - `POST /verify` — fixed price per verification call.
  - `POST /verify/graded` — the settlement amount is reduced when the VOP
    verdict comes back `PARTIAL`, using x402's own built-in
    `set_settlement_overrides()` mechanism.
- `generate_entity_secret.py` / `circle_client.py` / `create_wallet.py` —
  provision a real Base Sepolia receiving wallet via [Circle's
  Developer-Controlled Wallets](https://developers.circle.com/wallets/dev-controlled)
  API, for use as `X402_PAY_TO_ADDRESS` above.
- `generate_test_payer.py` / `test_payment.py` — a throwaway local test
  wallet that actually signs and submits an x402 payment against a running
  `x402_verify_gateway.py`, end to end, so you can verify the whole flow
  without a browser wallet or manual signing.

This whole path (server → Circle wallet → signed payment → VOP verdict)
has been run and verified end to end on Base Sepolia testnet.

## Quickstart

### 1. Run the paywalled verification server

```bash
pip install "x402[fastapi]" httpx python-dotenv uvicorn

export AGENTIC_SETTLE_API_KEY="your-key"       # free key at agenticsettle.io
export X402_PAY_TO_ADDRESS="0xYourWalletAddress"

uvicorn x402_verify_gateway:app --port 4021
```

Then, from an x402-capable client, `POST` to `http://localhost:4021/verify`
with:

```json
{
  "request_content": "Write a one-paragraph summary of photosynthesis.",
  "result_content": "Photosynthesis is the process by which plants..."
}
```

The first response is `402 Payment Required` with the payment terms
(network, asset, amount, recipient). The client signs a payment
authorization and retries; on success the response is the VOP verdict
(`PASS` / `PARTIAL` / `FAIL`, score, tier) exactly as returned by
AgenticSettle's core API.

### 2. Don't have a receiving wallet yet? Provision one with Circle

Requires a free [Circle Console](https://console.circle.com) account and a
Standard API key (see [Circle's entity secret
docs](https://developers.circle.com/wallets/dev-controlled/entity-secret-management)
for the one-time setup — this generates and registers a 32-byte entity
secret that authorizes the calls below; the raw secret and recovery file
never leave your machine and are never sent anywhere except Circle's API).

```bash
pip install pycryptodome httpx

export CIRCLE_API_KEY="your-circle-api-key"

# One-time: generates a fresh entity secret and prints the ciphertext to
# paste into Circle Console -> Configurator -> Entity Secret.
python generate_entity_secret.py

# After registering the ciphertext in the console:
python create_wallet.py
```

`create_wallet.py` creates a Wallet Set and one EOA wallet on Base Sepolia
via Circle's Developer-Controlled Wallets API, and prints the address to
use as `X402_PAY_TO_ADDRESS`.

### 3. Test the full payment flow end to end

```bash
pip install "x402[httpx]" eth-account

# Creates a local throwaway signing wallet (private key never printed —
# written to test_payer.local.txt, gitignored).
python generate_test_payer.py

# Fund the printed address with testnet USDC on Base Sepolia:
#   https://faucet.circle.com (select Base Sepolia + USDC)

# With x402_verify_gateway.py running in another terminal:
python test_payment.py
```

`test_payment.py` signs and submits a real x402 payment against the
running server and prints the resulting VOP verdict — confirming the
entire loop (agent pays → payment settles → verification runs → result
returned) works without any human in the loop.

## Why this exists

x402 answers *how* an AI agent pays. AgenticSettle answers *whether it
should pay, and how much* — based on whether the agent's output actually
meets the buyer's criteria. This demo is the minimal glue between the two:
a verification call that's itself paid for autonomously, and a settlement
amount that can scale with the quality of what's being verified.

## Configuration reference

| Env var                   | Default                              | Purpose                          |
|----------------------------|---------------------------------------|-----------------------------------|
| `AGENTIC_SETTLE_API_KEY`   | (required)                            | AgenticSettle API key             |
| `AGENTIC_SETTLE_BASE_URL`  | `https://app.agenticsettle.io`        | AgenticSettle backend             |
| `X402_PAY_TO_ADDRESS`      | (required for real payments)          | Wallet receiving payment          |
| `X402_FACILITATOR_URL`     | `https://x402.org/facilitator`        | x402 facilitator (testnet)        |
| `X402_NETWORK`             | `eip155:84532` (Base Sepolia)         | CAIP-2 network id                 |
| `X402_PRICE_USD`           | `$0.01`                               | Price per verification call       |

## Links

- [AgenticSettle](https://agenticsettle.io)
- [x402 protocol](https://github.com/coinbase/x402)
- [Circle Agent Stack](https://www.circle.com/agent-stack)

## License

MIT — see [LICENSE](LICENSE).
