#!/usr/bin/env python3
"""Phase 4 setup: configure Libredesk AI providers to use the local Gemini
forwarding proxy, and create the Premium Books AI assistant.

- Completion/embedding base URL: http://localhost:18080 (gemini-proxy.py).
  Libredesk appends "/chat/completions" / "/embeddings" to the base URL, so
  it must be configured WITH the /v1 prefix: http://localhost:18080/v1.
  The proxy strips that /v1 prefix when forwarding upstream.
- The api_key sent to Libredesk is a DUMMY placeholder; the proxy drops it
  and injects the real stored Gemini credential on egress. The real key
  value is never written to any file, log, or config by this script.
- The Libredesk agent login password is read at runtime from the existing
  phase-2-test.py (Phase 2 test login); this script writes no new copy of it.
- Completion model: gemini-3-flash-preview (gemini-2.5-flash is listed by
  the models endpoint but the API rejects completions for it as
  unavailable to new users; verified 2026-11-16 via the proxy).
- Embedding model: gemini-embedding-001, dimensions 768 (text-embedding-004
  is not in this key's model list).
"""
import json, re, sys
import requests

BASE = "http://localhost:9000"
PROXY = "http://localhost:18080/v1"
DUMMY_KEY = "proxy-placeholder-key"

with open("phase-2-test.py") as f:
    m = re.search(r'"password":\s*"([^"]+)"', f.read())
PASSWORD = m.group(1)

COMPLETION = {
    "provider": "openai",
    "base_url": PROXY,
    "api_key": DUMMY_KEY,
    "model": "gemini-3-flash-preview",
    "max_tokens": 1024,
    "dimensions": 0,
    "embedding_max_tokens": 0,
    "instructions": (
        "You are the Premium Books Library assistant. Answer only about books "
        "in the Premium Books Library catalogue, using only the knowledge base. "
        "When a visitor asks for a book by name or type, name the matching book "
        "titles, authors and categories from the knowledge base. If no book "
        "matches, say so plainly and do not invent a title. Answer in the "
        "visitor's language (Urdu or English)."
    ),
    "vision": False,
}
EMBEDDING = {
    "provider": "openai",
    "base_url": PROXY,
    "api_key": DUMMY_KEY,
    "model": "gemini-embedding-001",
    "max_tokens": 0,
    "dimensions": 768,
    "embedding_max_tokens": 2048,
    "instructions": "",
    "vision": False,
}

ASSISTANT = {
    "name": "Premium Books Assistant",
    "description": "Answers visitors' book questions from the Premium Books Library catalogue.",
    "instructions": (
        "You help visitors of Premium Books Library find books. "
        "Always search the knowledge base first. Answer only from what it returns: "
        "give the matching book title, author and category. If the visitor asks by "
        "type or category, suggest two or three matching books from the catalogue. "
        "If no book in the catalogue matches, say plainly that the book is not in "
        "the library and offer to help find a similar one. Never invent a book, "
        "author or link. Keep replies short."
    ),
    "guardrails": (
        "Never invent book titles, authors, categories or download links. "
        "Only name books that the knowledge base returned for this question."
    ),
    "expectation": "Short book suggestions with title, author and category, grounded in the catalogue.",
    "tone": "friendly",
    "response_length": "balanced",
    "max_turns": 10,
    "citations_enabled": True,
    "handoff_enabled": True,
    "enabled": True,
}

s = requests.Session()
r = s.post(f"{BASE}/api/v1/auth/login", json={"email": "System", "password": PASSWORD})
print("login:", r.status_code, r.text[:200])
assert r.status_code == 200, "login failed"
csrf = s.cookies.get("csrf_token", "")
H = {"X-CSRFTOKEN": csrf} if csrf else {}

def put_config(kind, payload):
    r = s.put(f"{BASE}/api/v1/ai/config/{kind}", json=payload, headers=H)
    print(f"PUT ai/config/{kind}:", r.status_code, r.text[:300])
    assert r.status_code == 200, f"{kind} config update failed: {r.text[:300]}"
    r = s.post(f"{BASE}/api/v1/ai/config/{kind}/test", json=payload, headers=H)
    print(f"POST ai/config/{kind}/test:", r.status_code, r.text[:300])
    assert r.status_code == 200, f"{kind} config test failed: {r.text[:300]}"
    r = s.get(f"{BASE}/api/v1/ai/config/{kind}", headers=H)
    cfg = r.json()
    print(f"GET ai/config/{kind}:", json.dumps(cfg)[:400])
    return cfg

put_config("completion", COMPLETION)
put_config("embedding", EMBEDDING)

# Create (or reuse) the assistant.
r = s.get(f"{BASE}/api/v1/ai/assistants", headers=H)
existing = [a for a in (r.json().get("data") or []) if a.get("name") == ASSISTANT["name"]]
if existing:
    assistant = existing[0]
    print("assistant already exists:", assistant["id"], "user_id:", assistant.get("user_id"))
else:
    files = {"data": (None, json.dumps(ASSISTANT), "application/json")}
    r = s.post(f"{BASE}/api/v1/ai/assistants", files=files, headers=H)
    print("POST ai/assistants:", r.status_code, r.text[:400])
    assert r.status_code == 200, f"assistant create failed: {r.text[:400]}"
    assistant = r.json()["data"]

with open("phase-4-state.json", "w") as f:
    json.dump({
        "completion_model": COMPLETION["model"],
        "embedding_model": EMBEDDING["model"],
        "embedding_dimensions": 768,
        "proxy_base_url": PROXY,
        "assistant_id": assistant["id"],
        "assistant_user_id": assistant.get("user_id"),
        "assistant_name": assistant["name"],
    }, f, indent=2)
print("assistant:", assistant["id"], "user_id:", assistant.get("user_id"))
print("OK — providers configured and tested, assistant ready")
