#!/usr/bin/env python3
"""Phase 4: update the AI assistant + completion-provider instructions so
every book answer carries the book LINK (title, author, category, site,
and Link from the knowledge base entry). Never invent a link.

Also re-asserts the multi-site design: one combined system, one assistant
and one knowledge base shared by one inbox per book website.
Login password is read at runtime from the existing phase-2-test.py.
"""
import json
import re

import requests

BASE = "http://localhost:9000"
MASKED_KEY = "•" * 10  # keeps the stored (dummy placeholder) key unchanged

with open("phase-2-test.py") as f:
    PASSWORD = re.search(r'"password":\s*"([^"]+)"', f.read()).group(1)
with open("phase-4-state.json") as f:
    STATE = json.load(f)

s = requests.Session()
r = s.post(f"{BASE}/api/v1/auth/login", json={"email": "System", "password": PASSWORD})
assert r.status_code == 200, "login failed"
csrf = s.cookies.get("csrf_token", "")
H = {"X-CSRFTOKEN": csrf} if csrf else {}

COMPLETION_INSTRUCTIONS = (
    "You are the book-library assistant for a combined system covering "
    "several book websites (each website has its own inbox; they share one "
    "assistant and one knowledge base). Answer only about books in the "
    "knowledge base, using only what it returns. When a visitor asks for a "
    "book by name or type, name the matching books with title, author, "
    "category, the site name, AND the Link from the knowledge base entry — "
    "every book you name must come with its Link. If no book matches, say "
    "so plainly and do not invent a title or a link. Answer in the "
    "visitor's language (Urdu or English)."
)
r = s.put(f"{BASE}/api/v1/ai/config/completion", json={
    "provider": "openai", "base_url": "http://localhost:18080/v1",
    "api_key": MASKED_KEY, "model": STATE["completion_model"],
    "max_tokens": 1024, "dimensions": 0, "embedding_max_tokens": 0,
    "instructions": COMPLETION_INSTRUCTIONS, "vision": False,
}, headers=H)
print("PUT completion config:", r.status_code, r.text[:200])
assert r.status_code == 200

ASSISTANT = {
    "name": "Premium Books Assistant",
    "description": "Answers visitors' book questions from the combined book-library catalogue, with a link for every book.",
    "instructions": (
        "You help visitors of the book-library websites find books. "
        "Always search the knowledge base first. Answer only from what it returns. "
        "For every book you name, give all of these: title, author, category, "
        "the site name, and the Link exactly as given in the knowledge base entry. "
        "If the visitor asks by type or category, suggest two or three matching "
        "books from the catalogue, each with its Link. If no book in the catalogue "
        "matches, say plainly that the book is not in the library and offer to help "
        "find a similar one. Never invent a book, author, category or link. "
        "Keep replies short."
    ),
    "guardrails": (
        "Never invent book titles, authors, categories or links. "
        "Only share the Link exactly as given in the knowledge base entry; "
        "if an entry has no link, do not make one up."
    ),
    "expectation": "Short book suggestions with title, author, category, site and Link, grounded in the catalogue.",
    "tone": "friendly",
    "response_length": "balanced",
    "max_turns": 10,
    "citations_enabled": True,
    "handoff_enabled": True,
    "enabled": True,
}
files = {"data": (None, json.dumps(ASSISTANT), "application/json")}
r = s.put(f"{BASE}/api/v1/ai/assistants/{STATE['assistant_id']}", files=files, headers=H)
print("PUT assistant:", r.status_code, r.text[:300])
assert r.status_code == 200
print("OK — instructions updated (assistant + completion provider)")
