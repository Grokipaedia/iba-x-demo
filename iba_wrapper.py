"""
iba_wrapper.py — Intent-Bound Authorization wrapper for xAI's Phoenix pipeline
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Every call to Phoenix must carry a signed intent token.
No token → blocked. Wrong scope → blocked. Expired → blocked.

Usage:
    python iba_wrapper.py

Then POST to http://localhost:8080/recommend with:
    Headers: X-IBA-Intent: <token>
    Body:    {"user_id": "...", "candidate_ids": [...]}

Generate a token:
    python iba_wrapper.py --gen-token --signer "your.name" --scope RECOMMEND

Author: Jeffrey Williams — IBA@intentbound.com — IntentBound.com
Patent GB2603013.0 (Pending) · PCT 150+ Countries
"""

import hashlib
import hmac
import json
import time
import uuid
import argparse
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# ─── CONFIG ──────────────────────────────────────────────────────────────────

SECRET_KEY = os.environ.get("IBA_SECRET", "iba-demo-secret-change-in-production")
TOKEN_TTL  = 300   # seconds
PHOENIX_HOST = "localhost"
PHOENIX_PORT = 8888  # adjust to your Phoenix run_pipeline.py port

VALID_SCOPES = {"RECOMMEND", "RERANK", "FILTER", "EXPLAIN"}

# ─── INTENT TOKEN ────────────────────────────────────────────────────────────

def generate_token(signer: str, scope: str, ttl: int = TOKEN_TTL) -> dict:
    """
    Create a signed IBA intent token.
    Structure: {intent_id, signer, scope, issued_at, expires_at, signature}
    """
    if scope not in VALID_SCOPES:
        raise ValueError(f"Invalid scope '{scope}'. Must be one of: {VALID_SCOPES}")

    intent_id  = str(uuid.uuid4())
    issued_at  = int(time.time())
    expires_at = issued_at + ttl

    payload = f"{intent_id}:{signer}:{scope}:{issued_at}:{expires_at}"
    signature = hmac.new(
        SECRET_KEY.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()

    token = {
        "intent_id":  intent_id,
        "signer":     signer,
        "scope":      scope,
        "issued_at":  issued_at,
        "expires_at": expires_at,
        "signature":  signature,
    }
    encoded = json.dumps(token, separators=(",", ":"))
    return {"token": encoded, "hash": signature[:16] + "..."}


def verify_token(encoded: str) -> tuple[bool, str, dict]:
    """
    Verify an IBA intent token.
    Returns (valid: bool, reason: str, claims: dict)
    """
    try:
        token = json.loads(encoded)
    except Exception:
        return False, "Invalid token format", {}

    required = {"intent_id", "signer", "scope", "issued_at", "expires_at", "signature"}
    if not required.issubset(token.keys()):
        return False, "Missing required token fields", {}

    # Check expiry
    now = int(time.time())
    if now > token["expires_at"]:
        return False, f"Token expired {now - token['expires_at']}s ago", {}

    # Verify scope
    if token["scope"] not in VALID_SCOPES:
        return False, f"Unknown scope: {token['scope']}", {}

    # Verify signature
    payload = f"{token['intent_id']}:{token['signer']}:{token['scope']}:{token['issued_at']}:{token['expires_at']}"
    expected_sig = hmac.new(
        SECRET_KEY.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, token["signature"]):
        return False, "Signature mismatch — token tampered or wrong key", {}

    return True, "OK", token


# ─── AUDIT LOG ───────────────────────────────────────────────────────────────

def audit(event: str, intent_id: str, signer: str = "-", scope: str = "-", note: str = ""):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] [{event:8s}] intent={intent_id[:8]}... signer={signer} scope={scope}"
    if note:
        line += f" | {note}"
    print(line, flush=True)


# ─── HTTP HANDLER ────────────────────────────────────────────────────────────

class IBAGateway(BaseHTTPRequestHandler):
    """
    Minimal HTTP gateway. Validates IBA intent before forwarding to Phoenix.
    """

    def log_message(self, format, *args):
        pass  # suppress default HTTP logs — we use audit()

    def send_json(self, code: int, body: dict):
        data = json.dumps(body, indent=2).encode()
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

    def _handle_recommend(self):
        """Gate: verify IBA intent → forward to Phoenix → log."""
        token_header = self.headers.get("X-IBA-Intent", "")

        if not token_header:
            audit("BLOCKED", "none", note="No X-IBA-Intent header")
            self.send_json(401, {
                "error": "IBA intent token required",
                "hint":  "Set header X-IBA-Intent: <token>  — generate one at POST /token"
            })
            return

        valid, reason, claims = verify_token(token_header)

        if not valid:
            audit("BLOCKED", claims.get("intent_id", "?"), note=reason)
            self.send_json(403, {"error": f"Intent verification failed: {reason}"})
            return

        # Intent verified — read request body
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.raw_requestline) if length == 0 else json.loads(self.rfile.read(length))

        audit("VERIFIED", claims["intent_id"], claims["signer"], claims["scope"])

        # ── Forward to Phoenix ──────────────────────────────────────────────
        # In a real deployment, proxy to Phoenix's HTTP API.
        # For this demo we return a mock response showing IBA interception worked.
        result = self._call_phoenix(body, claims)

        audit("DELIVERED", claims["intent_id"], claims["signer"], claims["scope"],
              note=f"returned {len(result.get('recommendations', []))} items")

        self.send_json(200, {
            "intent_id":       claims["intent_id"],
            "signer":          claims["signer"],
            "scope":           claims["scope"],
            "recommendations": result["recommendations"],
            "iba_audit_ref":   f"txn_{claims['intent_id'][:8]}",
        })

    def _call_phoenix(self, body: dict, claims: dict) -> dict:
        """
        Stub: replace with actual Phoenix HTTP call or subprocess invocation.
        Example real call:
            import urllib.request
            req = urllib.request.Request(
                f"http://{PHOENIX_HOST}:{PHOENIX_PORT}/recommend",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req) as r:
                return json.loads(r.read())
        """
        # Demo stub — replace with real Phoenix call
        candidates = body.get("candidate_ids", list(range(48)))
        return {
            "recommendations": candidates[:10],
            "pipeline": "phoenix+grox",
            "note": "stub — connect to real Phoenix for live results"
        }

    def _handle_token_gen(self):
        """Generate a demo intent token (for development use)."""
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length)) if length else {}

        signer = body.get("signer", "demo-user")
        scope  = body.get("scope", "RECOMMEND")
        ttl    = int(body.get("ttl", TOKEN_TTL))

        try:
            result = generate_token(signer, scope, ttl)
            audit("TOKEN_GEN", "new", signer, scope, note=f"ttl={ttl}s")
            self.send_json(200, result)
        except ValueError as e:
            self.send_json(400, {"error": str(e)})


# ─── CLI ─────────────────────────────────────────────────────────────────────

def cli():
    parser = argparse.ArgumentParser(description="IBA × X — Intent-Bound Authorization wrapper")
    parser.add_argument("--port",      type=int, default=8080,      help="Gateway port (default: 8080)")
    parser.add_argument("--gen-token", action="store_true",         help="Generate a token and exit")
    parser.add_argument("--signer",    default="jeffrey.williams",  help="Token signer identity")
    parser.add_argument("--scope",     default="RECOMMEND",         help=f"Intent scope: {VALID_SCOPES}")
    parser.add_argument("--ttl",       type=int, default=TOKEN_TTL, help="Token TTL in seconds")
    args = parser.parse_args()

    if args.gen_token:
        try:
            result = generate_token(args.signer, args.scope, args.ttl)
            print("\n── IBA Intent Token ──────────────────────────────────────────")
            print(f"  Signer : {args.signer}")
            print(f"  Scope  : {args.scope}")
            print(f"  TTL    : {args.ttl}s")
            print(f"  Hash   : {result['hash']}")
            print(f"\n  Token  :\n  {result['token']}")
            print("\n  Usage  : curl -X POST http://localhost:8080/recommend \\")
            print(f"             -H 'X-IBA-Intent: {result['token']}' \\")
            print("             -H 'Content-Type: application/json' \\")
            print("             -d '{\"candidate_ids\": [1,2,3,4,5]}'")
            print("──────────────────────────────────────────────────────────────\n")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    print(f"""
╔══════════════════════════════════════════════════════════╗
║         IBA × X — Intent-Bound Authorization             ║
║         Wrapping xAI's Phoenix + Grox pipeline           ║
╚══════════════════════════════════════════════════════════╝
  Gateway : http://localhost:{args.port}
  Scopes  : {', '.join(sorted(VALID_SCOPES))}
  Token TTL: {TOKEN_TTL}s

  Endpoints:
    GET  /health      — liveness check
    POST /recommend   — governed recommendation (requires X-IBA-Intent header)
    POST /token       — generate demo intent token

  Quick test:
    python iba_wrapper.py --gen-token  →  then POST with token

  IntentBound.com · IBA@intentbound.com
──────────────────────────────────────────────────────────
""")

    server = HTTPServer(("", args.port), IBAGateway)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  IBA gateway stopped.")


if __name__ == "__main__":
    # Fix hmac.new → hmac.new is not valid; use hmac.new() correctly
    import hmac as _hmac
    _orig_new = _hmac.new
    cli()
