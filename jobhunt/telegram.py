"""Telegram: digest out, questions out, your replies in (reply to the question message).

Uses getUpdates directly. Give the agent its OWN bot: if another program polls the same bot token,
the two will steal each other's messages and answers will go missing. Setup: docs/TELEGRAM.md."""
import os
import time

import httpx

from .common import log, save_answer, set_env_value
from .store import kv_get, kv_set, now

API = "https://api.telegram.org/bot{}/{}"


def _call(method: str, token: str | None = None, **params):
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return None
    try:
        data = httpx.post(API.format(token, method), json=params, timeout=30).json()
    except httpx.HTTPError as e:  # Telegram is optional: never let it kill a run
        log.warning("telegram %s unreachable: %s", method, type(e).__name__)
        return None
    if not data.get("ok"):
        log.warning("telegram %s failed: %s", method, data.get("description"))
        return None
    return data["result"]


def chat_id() -> str | None:
    return os.environ.get("TELEGRAM_CHAT_ID") or None


def send(text: str) -> int | None:
    cid = chat_id()
    if not cid or not os.environ.get("TELEGRAM_BOT_TOKEN"):
        log.info("telegram not configured; message:\n%s", text)
        return None
    msg_id = None
    for i in range(0, len(text), 3900):  # Telegram caps messages at 4096 chars
        res = _call("sendMessage", chat_id=cid, text=text[i:i + 3900], disable_web_page_preview=True)
        msg_id = msg_id or (res or {}).get("message_id")
    return msg_id


def ask(db, section: str, key: str | None, prompt: str) -> None:
    """Ask once. Same (section, key/prompt) is never re-asked while pending or answered."""
    dedupe_key = key or prompt
    if db.execute("SELECT 1 FROM questions WHERE section=? AND COALESCE(key, prompt)=?", (section, dedupe_key)).fetchone():
        return
    msg_id = send(f"❓ Job Hunter needs input\n\n{prompt}\n\n↩️ Reply to THIS message with your answer.")
    db.execute("INSERT INTO questions (section, key, prompt, telegram_msg_id, asked_at) VALUES (?,?,?,?,?)",
               (section, key, prompt, msg_id, now()))


def collect_answers(db) -> int:
    """Pull replies to pending questions and save them to data/answers.yaml."""
    offset = kv_get(db, "tg_offset", 0)
    updates = _call("getUpdates", offset=offset, timeout=0, allowed_updates=["message"]) or []
    allowed = chat_id()
    got = 0
    for u in updates:
        offset = max(offset, u["update_id"] + 1)
        msg = u.get("message") or {}
        reply_to = (msg.get("reply_to_message") or {}).get("message_id")
        if not reply_to or str(msg.get("chat", {}).get("id")) != str(allowed):  # only you can answer
            continue
        q = db.execute("SELECT * FROM questions WHERE telegram_msg_id=? AND answered_at IS NULL", (reply_to,)).fetchone()
        if not q:
            continue
        answer = msg.get("text", "").strip()
        if q["section"] == "application_defaults":
            save_answer("application_defaults", q["key"], answer)
        else:
            save_answer("extra_facts", None, f"Q: {q['prompt']} A: {answer}")
        db.execute("UPDATE questions SET answer=?, answered_at=? WHERE id=?", (answer, now(), q["id"]))
        got += 1
    kv_set(db, "tg_offset", offset)
    return got


def setup() -> None:
    """Interactive: verify the bot token, capture your chat id from a message you send, save it, send a test."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        token = input("Paste the bot token from @BotFather (it looks like 123456:ABC-...): ").strip()
    me = _call("getMe", token=token)
    if not me:
        raise SystemExit("Telegram rejected that token. Copy it again from @BotFather (/mybots -> your bot -> API Token).")
    if (_call("getWebhookInfo", token=token) or {}).get("url"):
        raise SystemExit("This bot has a webhook set, so it is used by another program. Create a new bot for the agent.")
    set_env_value("TELEGRAM_BOT_TOKEN", token)
    print(f"Bot OK: @{me['username']}. Open Telegram, find @{me['username']}, press Start, and send it any message.")
    print("Waiting up to 2 minutes for your message...")
    offset, deadline = 0, time.time() + 120
    while time.time() < deadline:
        for u in _call("getUpdates", token=token, offset=offset, timeout=20, allowed_updates=["message"]) or []:
            offset = u["update_id"] + 1
            chat = (u.get("message") or {}).get("chat") or {}
            if chat.get("type") == "private":
                set_env_value("TELEGRAM_CHAT_ID", str(chat["id"]))
                _call("getUpdates", token=token, offset=offset, timeout=0)  # acknowledge, so runs start clean
                os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"] = token, str(chat["id"])
                send("✅ Job Hunter is connected. Digests and questions will arrive here.\n"
                     "When I ask something, reply to THAT message.")
                print(f"Saved TELEGRAM_CHAT_ID={chat['id']} to .env and sent a test message. Done.")
                return
    raise SystemExit("No message arrived. Send your bot a message in a private chat, then run telegram-setup again.")
