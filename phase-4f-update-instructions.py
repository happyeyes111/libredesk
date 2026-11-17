#!/usr/bin/env python3
"""Phase 4 full load: update the AI assistant + completion-provider
instructions for the combined four-site system with DIRECT book-page links.

Cross-site rule: when a visitor in ANY inbox asks for a book that lives on
ANOTHER site, the assistant must say which site it is on, give title, author,
category and the Link exactly as in the knowledge base entry, so pressing the
link lands on that book's page. Never invent a title, author or link.
If no book matches in ANY of the four catalogues, say so plainly.

Login password is read at runtime from phase-2-test.py.
Assistant id/user_id are read from phase-4-state.json.
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

r = s.put(f"{BASE}/api/v1/ai/config/completion", json={
    "provider": "openai", "base_url": "http://localhost:18080/v1",
    "api_key": MASKED_KEY, "model": STATE["completion_model"],
    "max_tokens": 1024, "dimensions": 0, "embedding_max_tokens": 0,
    "instructions": COMPLETION_INSTRUCTIONS, "vision": False,
}, headers=H)
print("PUT completion config:", r.status_code, r.text[:200])
assert r.status_code == 200

aid = STATE["assistant_id"]
r = s.get(f"{BASE}/api/v1/ai/assistants/{aid}", headers=H)
print("GET assistant:", r.status_code)
cur = r.json().get("data") or {}
payload = {
    "name": cur.get("name", "Premium Books Assistant"),
    "description": "Answers visitors' book questions from the combined catalogue of all four book-library websites, with a direct link for every book.",
    "instructions": ASSISTANT_INSTRUCTIONS,
    "guardrails": ASSISTANT_GUARDRAILS,
    "expectation": cur.get("expectation", "Short book suggestions with title, author, category, site and Link, grounded in the catalogue."),
    "tone": cur.get("tone", "friendly"),
    "response_length": cur.get("response_length", "balanced"),
    "max_turns": cur.get("max_turns", 10),
    "citations_enabled": True,
    "handoff_enabled": True,
    "enabled": True,
}
files = {"data": (None, json.dumps(payload), "application/json")}
r = s.put(f"{BASE}/api/v1/ai/assistants/{aid}", files=files, headers=H)
print("PUT assistant:", r.status_code, r.text[:300])
assert r.status_code == 200, r.text[:300]
print("OK — cross-site instructions updated")
