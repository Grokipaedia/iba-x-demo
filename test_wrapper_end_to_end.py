import json, time, threading, urllib.request, urllib.error, sys
sys.path.insert(0, ".")
import iba_wrapper_v3 as w


def post(path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else b""
    req = urllib.request.Request(f"http://localhost:8083{path}", data=data,
        headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def get_token(scope, ttl=300):
    _, body = post("/token", {"signer": "test.user", "scope": scope, "ttl": ttl})
    return body["token"]


if __name__ == "__main__":
    server = w.HTTPServer(("", 8083), w.IBAGateway)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.3)

    print("=" * 70)
    print(" FLOW 1 — Standard 'For You' feed: RECOMMEND token on /recommend")
    print("=" * 70)
    tok = get_token("RECOMMEND")
    status, body = post("/recommend", {"candidate_ids": list(range(48))}, headers={"X-IBA-Intent": tok})
    print(f"HTTP {status} (expect 200) — {body.get('recommendations', body)[:5] if status==200 else body}\n")

    print("=" * 70)
    print(" FLOW 2 — Agent tries to exceed its scope: RECOMMEND token used on /rerank")
    print(" SCOPE.md claims: 403, 'Scope violation: RERANK requires explicit intent token'")
    print("=" * 70)
    tok = get_token("RECOMMEND")
    status, body = post("/rerank", {"candidate_ids": [1, 2, 3]}, headers={"X-IBA-Intent": tok})
    print(f"HTTP {status} (expect 403) — {body}\n")

    print("=" * 70)
    print(" FLOW 2b — Reverse check: RERANK token used on /recommend (the original gap)")
    print("=" * 70)
    tok = get_token("RERANK")
    status, body = post("/recommend", {"candidate_ids": [1, 2, 3]}, headers={"X-IBA-Intent": tok})
    print(f"HTTP {status} (expect 403, THIS is what silently passed before the fix) — {body}\n")

    print("=" * 70)
    print(" FLOW 3 — Legitimate multi-step flow: separate RECOMMEND then RERANK tokens")
    print("=" * 70)
    tok_a = get_token("RECOMMEND", ttl=300)
    status, body = post("/recommend", {"candidate_ids": list(range(1, 13))}, headers={"X-IBA-Intent": tok_a})
    print(f"Step A — RECOMMEND: HTTP {status} — got {body.get('recommendations')}")
    candidates = body.get("recommendations", [])

    tok_b = get_token("RERANK", ttl=60)
    status, body = post("/rerank", {"candidate_ids": candidates}, headers={"X-IBA-Intent": tok_b})
    print(f"Step B — RERANK (own token, shorter TTL): HTTP {status} — got {body.get('reranked')}")
    print(f"(reversed order proves the reranker actually ran, not a pass-through)\n")

    print("=" * 70)
    print(" FLOW 3b — FILTER and EXPLAIN, the other two scopes from the table")
    print("=" * 70)
    tok_f = get_token("FILTER")
    status, body = post("/filter", {"candidate_ids": [1,2,3,4,5], "exclude": [2,4]}, headers={"X-IBA-Intent": tok_f})
    print(f"FILTER: HTTP {status} — {body.get('filtered')} (excluded 2,4)")

    tok_e = get_token("EXPLAIN")
    status, body = post("/explain", {"candidate_ids": [1,2,3]}, headers={"X-IBA-Intent": tok_e})
    print(f"EXPLAIN: HTTP {status} — {body.get('explanations')}\n")

    print("=" * 70)
    print(" FLOW 4 — Expired token. SCOPE.md claims: 401 Unauthorized")
    print("=" * 70)
    tok = get_token("RECOMMEND", ttl=1)
    time.sleep(2)
    status, body = post("/recommend", {"candidate_ids": [1]}, headers={"X-IBA-Intent": tok})
    print(f"HTTP {status} (expect 401) — {body}\n")

    print("=" * 70)
    print(" Non-existent endpoint check (should no longer be 404 for the real four)")
    print("=" * 70)
    for path in ["/recommend", "/rerank", "/filter", "/explain"]:
        tok = get_token("EXPLAIN")  # deliberately wrong scope for all but /explain
        status, _ = post(path, {}, headers={"X-IBA-Intent": tok})
        print(f"  POST {path} with an EXPLAIN-scoped token: HTTP {status}")
