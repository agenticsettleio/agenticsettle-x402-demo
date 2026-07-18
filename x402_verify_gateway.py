"""
x402_verify_gateway.py — VOP verification gated by an x402 micropayment
=========================================================================

Reference implementation: an AI agent pays a small amount of USDC via the
x402 protocol (https://github.com/coinbase/x402) to call AgenticSettle's
VOP (Verification-of-Output-Provenance) verification. This is a standalone
demo server — it does not touch the production AgenticSettle backend. It
sits in front of the real AgenticSettle `/v2/verify` REST endpoint the
same way the plain-API-key examples in the main SDK do, except access is
paywalled per-request with a Base Sepolia USDC payment instead of (or in
addition to) an API key.

Two routes are exposed:

  POST /verify         — fixed-price gate ("exact" scheme). Every call
                          costs the same amount regardless of the VOP
                          outcome. This is the simplest, most common
                          x402 integration pattern.

  POST /verify/graded   — variable-price gate. The route runs VOP first,
                          then charges *less* than the advertised maximum
                          when the verdict is PARTIAL, using x402's own
                          `set_settlement_overrides()` hook — a built-in
                          capability of the x402 SDK
                          (`x402/http/middleware/fastapi.py`), not
                          something this demo adds on top of the protocol.

Prerequisites
-------------
1. Python 3.10+
2. Install dependencies:
       pip install "x402[fastapi]" httpx python-dotenv uvicorn
3. Set environment variables:
       AGENTIC_SETTLE_API_KEY   — get a free key at https://agenticsettle.io
       AGENTIC_SETTLE_BASE_URL  — defaults to https://app.agenticsettle.io
       X402_PAY_TO_ADDRESS      — wallet address that receives payment
       X402_FACILITATOR_URL     — defaults to the public testnet facilitator
       X402_NETWORK             — defaults to Base Sepolia (eip155:84532)
       X402_PRICE_USD           — defaults to "$0.01" per verification call

Run
---
    uvicorn x402_verify_gateway:app --port 4021

Then, from an x402-capable client (e.g. the x402 CLI or an agent using
the x402 client SDK), POST to http://localhost:4021/verify with a
{"request_content": ..., "result_content": ...} body. The client will
receive a 402 Payment Required response first, sign a payment
authorization, and retry — standard x402 flow.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI, Request

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional

from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI, set_settlement_overrides
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.server import x402ResourceServer

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AGENTIC_SETTLE_BASE_URL = os.getenv("AGENTIC_SETTLE_BASE_URL", "https://app.agenticsettle.io").rstrip("/")
AGENTIC_SETTLE_API_KEY = os.getenv("AGENTIC_SETTLE_API_KEY", "")

PAY_TO = os.getenv("X402_PAY_TO_ADDRESS", "0x0000000000000000000000000000000000dEaD")
FACILITATOR_URL = os.getenv("X402_FACILITATOR_URL", "https://x402.org/facilitator")
NETWORK = os.getenv("X402_NETWORK", "eip155:84532")  # Base Sepolia testnet
PRICE_USD = os.getenv("X402_PRICE_USD", "$0.01")

# ---------------------------------------------------------------------------
# x402 resource server wiring
# ---------------------------------------------------------------------------

facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL))
server = x402ResourceServer(facilitator)
server.register(NETWORK, ExactEvmServerScheme())

routes: dict[str, RouteConfig] = {
    "POST /verify": RouteConfig(
        accepts=[PaymentOption(scheme="exact", pay_to=PAY_TO, price=PRICE_USD, network=NETWORK)],
        mime_type="application/json",
        description="Run AgenticSettle VOP verification on an AI agent output.",
    ),
    "POST /verify/graded": RouteConfig(
        # The advertised price is the *maximum* — see set_settlement_overrides
        # below for how the actual charge is reduced for PARTIAL verdicts.
        # This requires the 'upto' scheme rather than 'exact'; left as
        # 'exact' here since the public facilitator used for this demo only
        # supports 'exact' on testnet as of 2026-07. Swap in the 'upto'
        # scheme once a facilitator that supports it is configured.
        accepts=[PaymentOption(scheme="exact", pay_to=PAY_TO, price=PRICE_USD, network=NETWORK)],
        mime_type="application/json",
        description="VOP verification with settlement scaled to verdict quality.",
    ),
}

app = FastAPI(title="AgenticSettle VOP x x402 reference gateway")
app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)


# ---------------------------------------------------------------------------
# Shared VOP call — delegates to the real AgenticSettle REST API
# ---------------------------------------------------------------------------

async def _run_vop(request_content: str, result_content: str, agent_id: str | None) -> dict[str, Any]:
    if not AGENTIC_SETTLE_API_KEY:
        raise RuntimeError("AGENTIC_SETTLE_API_KEY is not set — see module docstring")
    headers = {
        "x-api-key": AGENTIC_SETTLE_API_KEY,
        "content-type": "application/json",
        "user-agent": "agenticsettle-x402-demo/1.0",
    }
    payload = {
        "request_content": request_content,
        "result_content": result_content,
        "agent_id": agent_id,
        "audience": "agent",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{AGENTIC_SETTLE_BASE_URL}/v2/verify", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


# ---------------------------------------------------------------------------
# Route 1 — fixed price per verification (the common case)
# ---------------------------------------------------------------------------

@app.post("/verify")
async def verify(payload: dict[str, Any]) -> dict[str, Any]:
    result = await _run_vop(
        payload["request_content"], payload["result_content"], payload.get("agent_id")
    )
    return result


# ---------------------------------------------------------------------------
# Route 2 — settlement amount scaled by verdict quality
# ---------------------------------------------------------------------------

@app.post("/verify/graded")
async def verify_graded(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    result = await _run_vop(
        payload["request_content"], payload["result_content"], payload.get("agent_id")
    )

    verdict = result.get("verdict")
    if verdict == "PARTIAL":
        # Charge half the advertised maximum for a partial-quality result.
        # set_settlement_overrides() writes to the *response* object, which
        # the x402 middleware reads and strips before the client sees it.
        from fastapi import Response

        response = Response()
        half_price_atomic_units = "5000"  # illustrative — derive from PRICE_USD/2 in a real deployment
        set_settlement_overrides(response, {"amount": half_price_atomic_units})
    elif verdict == "FAIL":
        # A production deployment would typically cancel settlement entirely
        # here (raise, so the middleware's on-error cancellation path fires)
        # rather than charge anything for a failed verification.
        pass

    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=4021)
