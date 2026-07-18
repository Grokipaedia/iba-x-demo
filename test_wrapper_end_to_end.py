import json, time, threading, urllib.request, urllib.error, sys
sys.path.insert(0, ".")
import iba_wrapper_final as w

def post(path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else b""
    req = urllib.request.Request(f"http://localhost:8081{path}", data=data,
        headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

if __name__ == "__main__":
    server = w.HTTPServer(("", 8081), w.IBAGateway)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.3)

    print("SCENARIO 1 — valid token, valid request")
    status, body = post("/token", {"signer": "jeffrey.williams", "scope": "RECOMMEND"})
    token = body["token"]
    status, body = post("/recommend", {"candidate_ids": [1,2,3]}, headers={"X-IBA-Intent": token})
    print(f"  HTTP {status} (expect 200)\n")

    print("SCENARIO 2 — no token")
    status, body = post("/recommend", {"candidate_ids": [1]})
    print(f"  HTTP {status} (expect 401)\n")

    print("SCENARIO 3 — tampered token")
    tok = json.loads(token); tok["declared_intent"] = "EXPLAIN"
    status, body = post("/recommend", {"candidate_ids": [1]},
        headers={"X-IBA-Intent": json.dumps(tok, separators=(",",":"))})
    print(f"  HTTP {status} (expect 403) — {body.get('error','')[:60]}\n")

    print("SCENARIO 4 — expired token")
    status, body = post("/token", {"signer": "jeffrey.williams", "scope": "RECOMMEND", "ttl": 1})
    short = body["token"]; time.sleep(2)
    status, body = post("/recommend", {"candidate_ids": [1]}, headers={"X-IBA-Intent": short})
    print(f"  HTTP {status} (expect 403) — {body.get('error','')[:60]}\n")

    print("SCENARIO 5 — forged token (attacker's own keypair)")
    from iba_crypto import IntentCertificateV2, IBAKeyPair
    from dataclasses import asdict
    attacker = IBAKeyPair()
    forged_cert = IntentCertificateV2(agent_id="fake", principal="attacker",
        declared_intent="RECOMMEND", scope={}, hard_expiry_seconds=300)
    forged_cert.sign(attacker)
    status, body = post("/recommend", {"candidate_ids": [1]},
        headers={"X-IBA-Intent": json.dumps(asdict(forged_cert), separators=(",",":"))})
    print(f"  HTTP {status} (expect 403) — {body.get('error','')[:60]}\n")

    print("SCENARIO 6 — THE BUG: empty body, valid token")
    status, body = post("/token", {"signer": "jeffrey.williams", "scope": "RECOMMEND"})
    valid_token = body["token"]
    req = urllib.request.Request("http://localhost:8081/recommend", data=b"",
        headers={"X-IBA-Intent": valid_token}, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"  HTTP {resp.status} (expect 200, NOT a crash) — {resp.read()[:150]}")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} — {e.read()[:150]}")
    except Exception as e:
        print(f"  STILL CRASHING: {type(e).__name__}: {e}")
