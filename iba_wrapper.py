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


def verify_token(encoded: str, required_scope: str) -> tuple[bool, str, dict, int]:
    """
    Returns (valid, reason, claims, http_status).
    Status convention: 401 = authentication failed (bad/missing/expired/forged
    credentials — we don't know who this is, or don't trust them).
    403 = authentication succeeded, but the certificate's declared scope
    doesn't cover the specific action being requested (we know who this is,
    they're just not authorised for THIS).
    """
    try:
        token_dict = json.loads(encoded)
        cert = IntentCertificateV2(**token_dict)
    except Exception as e:
        return False, f"Invalid token format: {e}", {}, 401

    if cert.public_key_pem.strip() != TRUSTED_KEYS.public_key_pem().strip():
        return False, "Untrusted signer: public key does not match pinned trusted principal", {}, 401

    if not cert.verify():
        return False, "Signature invalid — token tampered or forged", {}, 401

    if (time.time() - cert.issued_at) >= cert.hard_expiry_seconds:
        return False, "Token expired — re-authorise to continue", {}, 401

    if cert.declared_intent not in VALID_SCOPES:
        return False, f"Unknown scope: {cert.declared_intent}", {}, 401

    # Authentication is fully valid at this point. Now check AUTHORIZATION:
    # does this specific certificate's scope cover the specific action requested?
    if cert.declared_intent != required_scope:
        return (False,
                f"Scope violation: {required_scope} requires an intent token scoped to "
                f"{required_scope}, this token is scoped to {cert.declared_intent}",
                token_dict, 403)

    return True, "OK", token_dict, 200


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
        route_map = {
            "/recommend": ("RECOMMEND", self._call_phoenix_recommend),
            "/rerank": ("RERANK", self._call_grox_rerank),
            "/filter": ("FILTER", self._call_phoenix_filter),
            "/explain": ("EXPLAIN", self._call_phoenix_explain),
        }
        if path in route_map:
            required_scope, action_fn = route_map[path]
            self._handle_governed_action(required_scope, action_fn)
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
        """FIX (carried from previous pass): empty/missing body returns {}
        instead of crashing on json.loads(self.raw_requestline)."""
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return {}

    def _handle_governed_action(self, required_scope: str, action_fn):
        """Single gate shared by all four scoped endpoints. This is the real
        fix for the gap found in SCOPE.md: a token is now checked against the
        SPECIFIC action being requested, not just against 'is this any valid
        scope string'. A RERANK token calling /recommend is rejected here."""
        token_header = self.headers.get("X-IBA-Intent", "")

        if not token_header:
            audit("BLOCKED", "none", note=f"No X-IBA-Intent header (required scope: {required_scope})")
            self.send_json(401, {
                "error": "IBA intent token required",
                "hint": "Set header X-IBA-Intent: <token> — generate one at POST /token"
            })
            return

        valid, reason, claims, status = verify_token(token_header, required_scope)

        if not valid:
            audit("BLOCKED", claims.get("agent_id", "?"), note=reason)
            self.send_json(status, {"error": reason})
            return

        body = self._read_body()
        audit("VERIFIED", claims["agent_id"], claims["principal"], claims["declared_intent"])

        result = action_fn(body, claims)

        audit("DELIVERED", claims["agent_id"], claims["principal"], claims["declared_intent"],
              note=f"{required_scope} — {result.get('summary', '')}")

        self.send_json(200, {
            "intent_id": claims["agent_id"],
            "signer": claims["principal"],
            "scope": claims["declared_intent"],
            **result,
            "iba_audit_ref": f"txn_{claims['agent_id'][:8]}",
        })

    def _call_phoenix_recommend(self, body: dict, claims: dict) -> dict:
        """Stub — real Phoenix integration is a separate task, not claimed as done here."""
        candidates = body.get("candidate_ids", list(range(48)))
        return {"recommendations": candidates[:10], "summary": f"{len(candidates[:10])} items",
                "note": "stub — connect to real Phoenix for live results"}

    def _call_grox_rerank(self, body: dict, claims: dict) -> dict:
        """Stub reranker — reverses order so the effect is visibly different
        from the input, making it obvious this actually ran rather than
        passing through untouched."""
        candidates = body.get("candidate_ids", [])
        reranked = list(reversed(candidates))
        return {"reranked": reranked, "summary": f"{len(reranked)} items reordered",
                "note": "stub reranker — connect to real Grox for live results"}

    def _call_phoenix_filter(self, body: dict, claims: dict) -> dict:
        candidates = body.get("candidate_ids", [])
        exclude = set(body.get("exclude", []))
        filtered = [c for c in candidates if c not in exclude]
        return {"filtered": filtered, "summary": f"{len(candidates) - len(filtered)} removed",
                "note": "stub filter — predicate is a simple exclude-list for this demo"}

    def _call_phoenix_explain(self, body: dict, claims: dict) -> dict:
        candidates = body.get("candidate_ids", [])
        explanation = [{"id": c, "reason": "stub scoring rationale — not real model output"} for c in candidates[:5]]
        return {"explanations": explanation, "summary": f"{len(explanation)} explained",
                "note": "stub explain — connect to real Phoenix scoring for live rationale"}

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
