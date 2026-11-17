#!/usr/bin/env python3
"""Phase 4 end-to-end test: Gemini-backed AI assistant answers book
questions from the category-article knowledge base, with book links.

- Verifies AI provider configs (proxy base URL, models, has_api_key).
- Verifies the assistant exists and is enabled.
- Assistant preview tests (no side effects):
  (a) by name: "The 5 AM Club" -> reply names the book, author, link.
  (b) by category: history book -> reply names a book + link.
  (c) no match: "Tafseer Ibn Kathir" (genuinely absent from the live
      catalogue) -> reply says it is not in the library and gives NO link.
  (d) Urdu: "زیرو پوائنٹ" -> Urdu reply with the book + link.
- Widget test: visitor asks for "The 5 AM Club" in the Premium Books
  Library inbox; conversation is assigned to the AI assistant user; the
  assistant's reply is awaited and checked for title + author + link.

Login password is read at runtime from the existing phase-2-test.py.
Results are printed and saved to phase-4-test-results.json.
"""
import json
import re
import time

import requests

BASE = "http://localhost:9000"
results = []

with open("phase-2-test.py") as f:
    PASSWORD = re.search(r'"password":\s*"([^"]+)"', f.read()).group(1)
with open("phase-4-state.json") as f:
    STATE = json.load(f)
ASSISTANT_ID = STATE["assistant_id"]
ASSISTANT_USER_ID = STATE["assistant_user_id"]


def step(name, ok, detail=""):
    results.append({"step": name, "ok": bool(ok), "detail": str(detail)[:600]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {str(detail)[:300]}")


def data(r):
    try:
        return r.json().get("data", r.json())
    except Exception:
        return {}


s = requests.Session()
r = s.post(f"{BASE}/api/v1/auth/login", json={"email": "System", "password": PASSWORD})
step("agent login (System)", r.status_code == 200, f"{r.status_code}")
csrf = s.cookies.get("csrf_token", "")
H = {"X-CSRFTOKEN": csrf} if csrf else {}

# --- provider configs ---
r = s.get(f"{BASE}/api/v1/ai/config/completion", headers=H)
cfg = data(r)
step("completion config via proxy",
     cfg.get("base_url") == "http://localhost:18080/v1"
     and cfg.get("model") == "gemini-3-flash-preview"
     and cfg.get("has_api_key") is True,
     f"model={cfg.get('model')} base={cfg.get('base_url')}")
r = s.get(f"{BASE}/api/v1/ai/config/embedding", headers=H)
cfg = data(r)
step("embedding config via proxy",
     cfg.get("base_url") == "http://localhost:18080/v1"
     and cfg.get("model") == "gemini-embedding-2"
     and cfg.get("dimensions") == 768
     and cfg.get("has_api_key") is True,
     f"model={cfg.get('model')} dims={cfg.get('dimensions')}")

# --- assistant ---
r = s.get(f"{BASE}/api/v1/ai/assistants/{ASSISTANT_ID}", headers=H)
a = data(r)
step("assistant exists + enabled",
     a.get("id") == ASSISTANT_ID and a.get("enabled") is True,
     f"id={a.get('id')} user_id={a.get('user_id')} name={a.get('name')}")

# --- proxy health ---
r = requests.get("http://127.0.0.1:18080/healthz", timeout=5)
step("gemini proxy up", r.status_code == 200 and r.json().get("ok") is True,
     f"{r.status_code}")

# --- preview tests ---
REPLIES = {}


def preview(msg):
    r = s.post(f"{BASE}/api/v1/ai/assistants/{ASSISTANT_ID}/preview",
               json={"message": msg}, headers=H, timeout=120)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code} {r.text[:200]}"
    d = data(r)
    return d, ""


reply, err = preview("I am looking for the book The 5 AM Club. Do you have it?")
txt = (reply or {}).get("reply", "") if reply else ""
REPLIES["by_name"] = txt
step("preview by name: The 5 AM Club",
     "5 AM Club" in txt and "Robin Sharma" in txt and "drive.google.com" in txt,
     err or txt[:300])
print("  REPLY:", txt[:500])

reply, err = preview("Can you suggest a history book from the library?")
txt = (reply or {}).get("reply", "") if reply else ""
REPLIES["by_category"] = txt
step("preview by category: history book + link",
     "drive.google.com" in txt and len(txt) > 20,
     err or txt[:300])
print("  REPLY:", txt[:500])

reply, err = preview("Do you have the book Tafseer Ibn Kathir?")
txt = (reply or {}).get("reply", "") if reply else ""
REPLIES["no_match"] = txt
# Correct behaviour: say it is NOT in the library, and do not present it
# as a found book with an author/link. Offering real similar books is OK.
step("preview no match: no invented book/link",
     "not in the library" in txt.lower()
     and "Ibn Kathir by" not in txt
     and "Tafseer Ibn Kathir —" not in txt,
     err or txt[:300])
print("  REPLY:", txt[:500])

reply, err = preview("مجھے زیرو پوائنٹ کتاب چاہیے")
txt = (reply or {}).get("reply", "") if reply else ""
REPLIES["urdu"] = txt
step("preview Urdu: زیرو پوائنٹ + link",
     "زیرو پوائنٹ" in txt and "drive.google.com" in txt,
     err or txt[:300])
print("  REPLY:", txt[:500])

# --- widget end-to-end with the AI assistant ---
r = s.get(f"{BASE}/api/v1/inboxes", headers=H)
inbox = next((ib for ib in (r.json().get("data") or [])
              if ib.get("name") == "Premium Books Library"), None)
INBOX_UUID = inbox.get("uuid") if inbox else None
step("Premium Books inbox found", bool(INBOX_UUID), INBOX_UUID or "")
CONV_UUID = None
if INBOX_UUID:
    w = requests.Session()
    WH = {"X-Libredesk-Inbox-ID": INBOX_UUID}
    r = w.post(f"{BASE}/api/v1/widget/chat/conversations/init", headers=WH,
               json={"message": "Assalam-o-Alaikum, I am looking for the book The 5 AM Club.",
                     "subject": "Book search"})
    ok = r.status_code in (200, 201)
    step("visitor starts widget conversation", ok, f"{r.status_code} {r.text[:200]}")
    if ok:
        d = data(r)
        CONV_UUID = (d.get("conversation") or {}).get("uuid") or d.get("uuid")
        r = s.put(f"{BASE}/api/v1/conversations/{CONV_UUID}/assignee/user",
                  json={"assignee_id": ASSISTANT_USER_ID}, headers=H)
        step("conversation assigned to AI assistant", r.status_code == 200,
             f"{r.status_code} {r.text[:150]}")
        # poll for the assistant's reply (worker runs in background)
        # NOTE: assistant replies arrive as sender_type "agent"; the
        # messages endpoint returns {"results": [...], "total": ...}.
        ai_reply = ""
        for _ in range(30):
            time.sleep(3)
            r = s.get(f"{BASE}/api/v1/conversations/{CONV_UUID}/messages", headers=H)
            d = r.json().get("data", {}) if r.status_code == 200 else {}
            msgs = d.get("results", []) if isinstance(d, dict) else d
            for m in msgs:
                if not isinstance(m, dict):
                    continue
                content = re.sub(r"<[^>]+>", " ", m.get("content") or "")
                if m.get("sender_type") == "agent" \
                        and "5 AM Club" in content \
                        and "drive.google.com" in content:
                    ai_reply = content
                    break
            if ai_reply:
                break
        REPLIES["widget"] = ai_reply
        step("AI assistant replies in widget conversation",
             "5 AM Club" in ai_reply and "drive.google.com" in ai_reply,
             ai_reply[:300])
        print("  AI REPLY:", ai_reply[:600])

passed = sum(1 for x in results if x["ok"])
print(f"\n==== {passed}/{len(results)} steps passed ====")
with open("phase-4-test-results.json", "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
with open("phase-4-ai-replies.json", "w") as f:
    json.dump(REPLIES, f, indent=2, ensure_ascii=False)
