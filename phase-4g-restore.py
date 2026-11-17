#!/usr/bin/env python3
"""Phase 4g restore: re-create the AI provider config + assistant on a FRESH
Libredesk DB (the VM reboot of 2026-11-17 ~03:34 UTC wiped Postgres again).
Same values as Phase 4/4f: completion gemini-3-flash-preview, embedding
gemini-embedding-2 (768 dims), base URL http://localhost:18080/v1 via the
local Gemini proxy, dummy placeholder key (real key never in any file).
Test calls to the provider are logged but NOT asserted: the embedding
free-tier quota is exhausted until ~08:00 UTC (13:00 PKT) 2026-11-17, so an
embedding test 429 is expected and must not abort the restore.
Writes updated phase-4-state.json with the new assistant id/user_id.
"""
import json
import re

import requests

BASE = "http://localhost:9000"
PROXY = "http://localhost:18080/v1"
DUMMY_KEY = "proxy-placeholder-key"

with open("phase-2-test.py") as f:
    PASSWORD = re.search(r'"password":\s*"([^"]+)"', f.read()).group(1)

COMPLETION_INSTRUCTIONS = (
    "You are the book-library assistant for a combined system covering four "
    "book websites: Premium Books Library, Urdu Free Books, Best Selling "
    "Books and The Unread Library. Each website has its own inbox; they share "
    "one assistant and one knowledge base covering all four catalogues. "
    "Answer only about books in the knowledge base, using only what it returns. "
    "When a visitor asks for a book by name or type, name the matching books "
    "with title, author, category, the site name, AND the Link from the "
    "knowledge base entry — every book you name must come with its Link. "
    "IMPORTANT: if the book lives on a DIFFERENT website than the one the "
    "visitor is chatting from, say so clearly — name that website and give "
    "its Link, so the visitor can press the link and land directly on that "
    "book's page. If no book matches in any of the four catalogues, say so "
    "plainly and do not invent a title or a link. Answer in the visitor's "
    "language (Urdu or English)."
)

ASSISTANT_INSTRUCTIONS = (
    "You help visitors of four book-library websites find books: Premium "
    "Books Library, Urdu Free Books, Best Selling Books and The Unread "
    "Library. Always search the knowledge base first. Answer only from what "
    "it returns. For every book you name, give all of these: title, author, "
    "category, the site name, and the Link exactly as given in the knowledge "
    "base entry. If the book is on a different website than the visitor's "
    "own site, say which website it is on and give its Link so the visitor "
    "can press it and land directly on that book's page. If the visitor asks "
    "by type or category, suggest two or three matching books from the "
    "catalogue, each with its Link. If no book in any catalogue matches, say "
    "plainly that the book is not in the library and offer to help find a "
    "similar one. Never invent a book, author, category or link. "
    "Keep replies short."
)

ASSISTANT_GUARDRAILS = (
    "Never invent book titles, authors, categories or download links. "
    "Only name books that the knowledge base returned for this question, "
    "with the Link exactly as given there."
)

s = requests.Session()
r = s.post(f"{BASE}/api/v1/auth/login", json={"email": "System", "password": PASSWORD})
assert r.status_code == 200, "login failed"
csrf = s.cookies.get("csrf_token", "")
H = {"X-CSRFTOKEN": csrf} if csrf else {}

def put_config(kind, payload):
    r = s.put(f"{BASE}/api/v1/ai/config/{kind}", json=payload, headers=H)
    print(f"PUT ai/config/{kind}:", r.status_code, r.text[:200], flush=True)
    assert r.status_code == 200, f"{kind} config failed: {r.text[:200]}"
    r = s.post(f"{BASE}/api/v1/ai/config/{kind}/test", json=payload, headers=H)
    print(f"POST ai/config/{kind}/test:", r.status_code, r.text[:200], flush=True)

put_config("completion", {
    "provider": "openai", "base_url": PROXY, "api_key": DUMMY_KEY,
    "model": "gemini-3-flash-preview", "max_tokens": 1024, "dimensions": 0,
    "embedding_max_tokens": 0, "instructions": COMPLETION_INSTRUCTIONS,
    "vision": False,
})
put_config("embedding", {
    "provider": "openai", "base_url": PROXY, "api_key": DUMMY_KEY,
    "model": "gemini-embedding-2", "max_tokens": 0, "dimensions": 768,
    "embedding_max_tokens": 2048, "instructions": "", "vision": False,
})

ASSISTANT = {
    "name": "Premium Books Assistant",
    "description": "Answers visitors' book questions from the combined catalogue of all four book-library websites, with a direct link for every book.",
    "instructions": ASSISTANT_INSTRUCTIONS,
    "guardrails": ASSISTANT_GUARDRAILS,
    "expectation": "Short book suggestions with title, author, category, site and Link, grounded in the catalogue.",
    "tone": "friendly", "response_length": "balanced", "max_turns": 10,
    "citations_enabled": True, "handoff_enabled": True, "enabled": True,
}
r = s.get(f"{BASE}/api/v1/ai/assistants", headers=H)
existing = [a for a in (r.json().get("data") or []) if a.get("name") == ASSISTANT["name"]]
if existing:
    assistant = existing[0]
    print("assistant already exists:", assistant["id"], "user_id:", assistant.get("user_id"), flush=True)
else:
    files = {"data": (None, json.dumps(ASSISTANT), "application/json")}
    r = s.post(f"{BASE}/api/v1/ai/assistants", files=files, headers=H)
    print("POST ai/assistants:", r.status_code, r.text[:400], flush=True)
    assert r.status_code == 200, f"assistant create failed: {r.text[:400]}"
    assistant = r.json()["data"]

state = {
    "completion_model": "gemini-3-flash-preview",
    "embedding_model": "gemini-embedding-2",
    "embedding_dimensions": 768,
    "proxy_base_url": PROXY,
    "assistant_id": assistant["id"],
    "assistant_user_id": assistant.get("user_id"),
    "assistant_name": "Premium Books Assistant",
}
json.dump(state, open("phase-4-state.json", "w"), indent=2)
print("STATE:", json.dumps(state), flush=True)
print("RESTORE DONE", flush=True)
