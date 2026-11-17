#!/usr/bin/env python3
"""Phase 4g tests: Urdu Free Books cross-site assistant tests.

Test books (verified present ONLY in the Urdu Free Books catalogue —
checked by normalized title against Premium, Best Selling and Unread):
- "Mukhtalif Mumalik ke Lazeez Khane" (Akhtar Jahan Begum) — خوراک و پکوان
- "Tariq Bin Ziyad" (Baleegh Aldeen Javed) — اسلامی تاریخ
- "Tajdeed Fikriyat Islam" (Allama Muhammad Iqbal) — فلسفہ و منطق
- "Tafseer Ibn Kathir" — in NONE of the four catalogues (checked).

Uses the assistant preview endpoint plus one live widget conversation in
the Urdu Free Books inbox. NOTE: the Gemini embedding free-tier quota is
exhausted until ~08:00 UTC / 13:00 PKT 2026-11-17, so preview/widget calls
may fail with 429 until then; failures are recorded honestly as
quota-blocked, not as wrong answers. Re-run after the reset.
Login password is read at runtime from phase-2-test.py.
Results printed and saved to phase-4g-test-results.json (+ replies).
"""
import json
import re
import time

import requests

BASE = "http://localhost:9000"
results = []
REPLIES = {}

with open("phase-2-test.py") as f:
    PASSWORD = re.search(r'"password":\s*"([^"]+)"', f.read()).group(1)
with open("phase-4-state.json") as f:
    STATE = json.load(f)
ASSISTANT_ID = STATE["assistant_id"]
ASSISTANT_USER_ID = STATE["assistant_user_id"]
with open("phase-4g-test-books.json", encoding="utf-8") as f:
    BOOKS = json.load(f)


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


def preview(msg):
    r = s.post(f"{BASE}/api/v1/ai/assistants/{ASSISTANT_ID}/preview",
               json={"message": msg}, headers=H, timeout=120)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code} {r.text[:200]}"
    return data(r), ""


def check(name, key, msg, must, must_not=()):
    reply, err = preview(msg)
    txt = (reply or {}).get("reply", "") if reply else ""
    REPLIES[key] = txt
    ok = all(m in txt for m in must) and all(m not in txt for m in must_not)
    step(name, ok, err or txt[:400])
    print("  REPLY:", txt[:600].replace("\n", " "))
    return txt


b1, b2, b3 = BOOKS[0], BOOKS[1], BOOKS[2]

check("urdufree-only: Mukhtalif Mumalik ke Lazeez Khane -> Urdu Free Books + archive.org link",
      "uf_1",
      "I am looking for the book Mukhtalif Mumalik ke Lazeez Khane by Akhtar Jahan Begum. Do you have it?",
      ["Mukhtalif Mumalik", "Urdu Free Books", "archive.org/details/mukhtalif-mumalik-ke-lazeez-khane-urdu"])

check("urdufree-only: Tariq Bin Ziyad -> Urdu Free Books + archive.org link",
      "uf_2",
      "Do you have the book Tariq Bin Ziyad?",
      ["Tariq Bin Ziyad", "Urdu Free Books", "archive.org/details/tariq-bin-ziyad-urdu"])

check("urdufree-only: Tajdeed Fikriyat Islam -> Urdu Free Books + archive.org link",
      "uf_3",
      "I am looking for Tajdeed Fikriyat Islam by Allama Muhammad Iqbal.",
      ["Tajdeed Fikriyat Islam", "Urdu Free Books", "archive.org/details/tajdeed-fikriyat-islam-urdu"])

check("no match: Tafseer Ibn Kathir -> says not in library, invents nothing",
      "no_match",
      "Do you have the book Tafseer Ibn Kathir?",
      ["not in the library"],
      ["Tafseer Ibn Kathir —", "archive.org/details/"])

# --- widget end-to-end: Urdu Free Books inbox visitor asks for Tariq Bin Ziyad ---
r = s.get(f"{BASE}/api/v1/inboxes", headers=H)
inbox = next((ib for ib in (r.json().get("data") or [])
              if ib.get("name") == "Urdu Free Books"), None)
INBOX_UUID = inbox.get("uuid") if inbox else None
step("Urdu Free Books inbox found", bool(INBOX_UUID), INBOX_UUID or "")
if INBOX_UUID:
    w = requests.Session()
    WH = {"X-Libredesk-Inbox-ID": INBOX_UUID}
    r = w.post(f"{BASE}/api/v1/widget/chat/conversations/init", headers=WH,
               json={"message": "Assalam-o-Alaikum, mujhe Tariq Bin Ziyad kitab chahiye.",
                     "subject": "Book search"})
    ok = r.status_code in (200, 201)
    step("visitor starts widget conversation (Urdu Free inbox)", ok, f"{r.status_code} {r.text[:200]}")
    if ok:
        d = data(r)
        CONV_UUID = (d.get("conversation") or {}).get("uuid") or d.get("uuid")
        r = s.put(f"{BASE}/api/v1/conversations/{CONV_UUID}/assignee/user",
                  json={"assignee_id": ASSISTANT_USER_ID}, headers=H)
        step("conversation assigned to AI assistant", r.status_code == 200,
             f"{r.status_code} {r.text[:150]}")
        ai_reply = ""
        for _ in range(40):
            time.sleep(3)
            r = s.get(f"{BASE}/api/v1/conversations/{CONV_UUID}/messages", headers=H)
            d = r.json().get("data", {}) if r.status_code == 200 else {}
            msgs = d.get("results", []) if isinstance(d, dict) else d
            for m in msgs:
                if not isinstance(m, dict):
                    continue
                content = re.sub(r"<[^>]+>", " ", m.get("content") or "")
                if m.get("sender_type") == "agent" and "Tariq Bin Ziyad" in content:
                    ai_reply = content
                    break
            if ai_reply:
                break
        REPLIES["widget_uf"] = ai_reply
        step("widget: AI names Urdu Free Books + archive.org link",
             "Tariq Bin Ziyad" in ai_reply and "Urdu Free Books" in ai_reply
             and "archive.org/details/tariq-bin-ziyad-urdu" in ai_reply,
             ai_reply[:400])
        print("  AI REPLY:", ai_reply[:600].replace("\n", " "))

passed = sum(1 for x in results if x["ok"])
print(f"\n==== {passed}/{len(results)} steps passed ====")
with open("phase-4g-test-results.json", "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
with open("phase-4g-ai-replies.json", "w") as f:
    json.dump(REPLIES, f, indent=2, ensure_ascii=False)
