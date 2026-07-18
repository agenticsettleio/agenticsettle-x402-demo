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

## Quickstart

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
