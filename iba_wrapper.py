"""
iba_wrapper.py — Intent-Bound Authorization wrapper for xAI's Phoenix pipeline
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This is the original iba_wrapper.py (real, working, HMAC-based), merged with
two fixes:

  1. A real bug: an empty-body POST with a valid token crashed the server
     (json.loads() was called on the raw HTTP request line, not the body,
     when Content-Length was 0). Confirmed via a live end-to-end test.
     Fixed below.

  2. The signing mechanism: upgraded from HMAC-SHA256 (a shared secret —
     the gateway that verifies tokens holds the same key that signs them)
     to real ECDSA P-256 asymmetric signing via iba_crypto.py (a private
     key signs; only the matching public key verifies; the verifier can
     never forge a token). This matches how "cryptographically signed" is
     described elsewhere in the IBA materials, and closes the gap
     identified in the Technical Specification, Section 6.

Also removed: dead code at the bottom of the original file
(`_orig_new = _hmac.new`) that did nothing.

Usage:
    python iba_wrapper.py

Then POST to http://localhost:8080/recommend with:
    Headers: X-IBA-Intent: <token>
    Body:    {"candidate_ids": [...]}

Generate a token:
    python iba_wrapper.py --gen-token --signer "your.name" --scope RECOMMEND

Author: Jeffrey Williams — IBA@intentbound.com — IntentBound.com
Patent GB2603013.0 (Pending) · PCT 150+ Countries
"""

import json
import time
import uuid
import argparse
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from dataclasses import asdict

from iba_crypto import IntentCertificateV2, IBAKeyPair

TOKEN_TTL = 300
VALID_SCOPES = {"RECOMMEND", "RERANK", "FILTER", "EXPLAIN"}

# The one keypair this gateway instance trusts. In a real deployment the
# private key lives with whoever is authorized to issue tokens (e.g. a
# signing service you control) — it is never held by, or transmitted to,
# the gateway that only needs to verify. Generating it here at startup is
# a demo convenience; production would load a pinned public key from config
# and keep the private key entirely separate.
TRUSTED_KEYS = IBAKeyPair()


def generate_token(signer: str, scope: str, ttl: int = TOKEN_TTL) -> dict:
    if scope not in VALID_SCOPES:
        raise ValueError(f"Invalid scope '{scope}'. Must be one of: {VALID_SCOPES}")

    cert = IntentCertificateV2(
        agent_id=str(uuid.uuid4()),
        principal=signer,
        declared_intent=scope,   # scope doubles as the declared intent for this simple demo
        scope={"allowed_scope": scope},
        hard_expiry_seconds=ttl,
    )
    cert.sign(TRUSTED_KEYS)
    encoded = json.dumps(asdict(cert), separators=(",", ":"))
    return {"token": encoded, "signature_preview": cert.signature[:16] + "..."}


def verify_token(encoded: str) -> tuple[bool, str, dict]:
    try:
        token_dict = json.loads(encoded)
        cert = IntentCertificateV2(**token_dict)
    except Exception as e:
        return False, f"Invalid token format: {e}", {}

    if cert.public_key_pem.strip() != TRUSTED_KEYS.public_key_pem().strip():
        return False, "Untrusted signer: public key does not match pinned trusted principal", {}

    if not cert.verify():
        return False, "Signature invalid — token tampered or forged", {}

    if (time.time() - cert.issued_at) >= cert.hard_expiry_seconds:
        return False, f"Token expired", {}

    if cert.declared_intent not in VALID_SCOPES:
        return False, f"Unknown scope: {cert.declared_intent}", {}

    return True, "OK", token_dict


def audit(event: str, intent_id: str, signer: str = "-", scope: str = "-", note: str = ""):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] [{event:8s}] intent={intent_id[:8]}... signer={signer} scope={scope}"
    if note:
        line += f" | {note}"
    print(line, flush=True)


class IBAGateway(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send_json(self, code: int, body: dict):
        data = json.dumps(body, indent=2, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/recommend":
            self._handle_recommend()
        elif path == "/token":
            self._handle_token_gen()
        else:
            self.send_json(404, {"error": "Unknown path"})

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"status": "IBA gateway active", "time": int(time.time())})
        else:
            self.send_json(404, {"error": "Not found"})

    def _read_body(self) -> dict:
        """FIX: previously called json.loads(self.raw_requestline) when
        Content-Length was 0, which always crashed — raw_requestline is the
        HTTP request line ('POST /recommend HTTP/1.1'), never JSON. An empty
        or missing body now correctly returns {} instead of raising."""
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return {}

    def _handle_recommend(self):
        token_header = self.headers.get("X-IBA-Intent", "")

        if not token_header:
            audit("BLOCKED", "none", note="No X-IBA-Intent header")
            self.send_json(401, {
                "error": "IBA intent token required",
                "hint": "Set header X-IBA-Intent: <token> — generate one at POST /token"
            })
            return

        valid, reason, claims = verify_token(token_header)

        if not valid:
            audit("BLOCKED", claims.get("agent_id", "?"), note=reason)
            self.send_json(403, {"error": f"Intent verification failed: {reason}"})
            return

        body = self._read_body()
        audit("VERIFIED", claims["agent_id"], claims["principal"], claims["declared_intent"])

        result = self._call_phoenix(body, claims)

        audit("DELIVERED", claims["agent_id"], claims["principal"], claims["declared_intent"],
              note=f"returned {len(result.get('recommendations', []))} items")

        self.send_json(200, {
            "intent_id": claims["agent_id"],
            "signer": claims["principal"],
            "scope": claims["declared_intent"],
            "recommendations": result["recommendations"],
            "iba_audit_ref": f"txn_{claims['agent_id'][:8]}",
        })

    def _call_phoenix(self, body: dict, claims: dict) -> dict:
        """Stub — same as the original file. Wiring this to a real Phoenix
        call is a separate integration task, not claimed as done here."""
        candidates = body.get("candidate_ids", list(range(48)))
        return {
            "recommendations": candidates[:10],
            "pipeline": "phoenix+grox",
            "note": "stub — connect to real Phoenix for live results",
        }

    def _handle_token_gen(self):
        body = self._read_body()
        signer = body.get("signer", "demo-user")
        scope = body.get("scope", "RECOMMEND")
        ttl = int(body.get("ttl", TOKEN_TTL))

        try:
            result = generate_token(signer, scope, ttl)
            audit("TOKEN_GEN", "new", signer, scope, note=f"ttl={ttl}s")
            self.send_json(200, result)
        except ValueError as e:
            self.send_json(400, {"error": str(e)})


def cli():
    parser = argparse.ArgumentParser(description="IBA × X — Intent-Bound Authorization wrapper")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--gen-token", action="store_true")
    parser.add_argument("--signer", default="jeffrey.williams")
    parser.add_argument("--scope", default="RECOMMEND")
    parser.add_argument("--ttl", type=int, default=TOKEN_TTL)
    args = parser.parse_args()

    if args.gen_token:
        try:
            result = generate_token(args.signer, args.scope, args.ttl)
            print(f"\nToken (signer={args.signer}, scope={args.scope}, ttl={args.ttl}s):")
            print(result["token"])
            token_val = result["token"]
            print(f"\ncurl -X POST http://localhost:{args.port}/recommend \\")
            print(f"  -H 'X-IBA-Intent: {token_val}' \\")
            print(f"  -H 'Content-Type: application/json' \\")
            print(f"  -d '{{\"candidate_ids\": [1,2,3,4,5]}}'")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    print(f"IBA Gateway listening on http://localhost:{args.port}")
    print(f"Scopes: {', '.join(sorted(VALID_SCOPES))} | Signing: ECDSA P-256 (real asymmetric)")
    server = HTTPServer(("", args.port), IBAGateway)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nIBA gateway stopped.")


if __name__ == "__main__":
    cli()
