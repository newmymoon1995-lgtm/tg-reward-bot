import json, uuid, urllib.request

import os
TOK = os.environ["BOT_TOKEN"]
CPAY = os.environ["CPAY_TOKEN"]
CHAT, OWNER = -1004403924410, 1867777631
REWARD, ASSET = "2.5", "USDT"
API = f"https://api.telegram.org/bot{TOK}/"

def call(method, **kw):
    body = json.dumps(kw).encode()
    req = urllib.request.Request(API + method, data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read())
    except Exception as e:
        try: return json.loads(e.read())
        except: return {"ok": False, "err": str(e)}

def pay(uid):
    body = json.dumps({"user_id": uid, "asset": ASSET, "amount": REWARD,
                       "spend_id": uuid.uuid4().hex[:32], "comment": "Ramp reward"}).encode()
    req = urllib.request.Request("https://pay.crypt.bot/api/transfer", data=body,
        headers={"Crypto-Pay-API-Token": CPAY, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read())
    except Exception as e:
        try: return json.loads(e.read())
        except: return {"ok": False}

st = json.load(open("state.json"))
left = set(st["left"]); pending = st["pending"]; done = set(st["done"])

updates = call("getUpdates", offset=st["offset"] + 1, timeout=0,
               allowed_updates=["message", "callback_query"]).get("result", [])

for u in updates:
    st["offset"] = u["update_id"]

    if "callback_query" in u:
        cb = u["callback_query"]
        call("answerCallbackQuery", callback_query_id=cb["id"])
        if cb["from"]["id"] != OWNER: continue
        data = cb.get("data", "")
        act, _, cid = data.partition(":")
        p = pending.pop(cid, None)
        if not p: continue
        tu, mid, chat_ = p["uid"], cb["message"]["message_id"], cb["message"]["chat"]["id"]
        if act == "pay":
            r = pay(tu)
            if r.get("ok"):
                done.add(tu)
                call("editMessageText", chat_id=chat_, message_id=mid, text=f"✅ PAID $2.50 USDT to {tu} (claim {cid})")
                call("sendMessage", chat_id=tu, text="🎉 You received $2.50 USDT via @CryptoBot — Ramp reward claimed!")
                call("sendMessage", chat_id=CHAT, text=f"🎉 A member just claimed the $2.50 USDT Ramp reward!")
            else:
                call("editMessageText", chat_id=chat_, message_id=mid, text=f"❌ Pay failed: {str(r)[:200]}")
        else:
            call("editMessageText", chat_id=chat_, message_id=mid, text=f"❌ Rejected claim {cid}")
            call("sendMessage", chat_id=tu, text="❌ Your proof was rejected — must show completed Ramp signup with code 8P84M0.")
        continue

    m = u.get("message") or u.get("edited_message")
    if not m: continue
    cid_ = m["chat"]["id"]
    frm = m.get("from", {})
    uid, text = frm.get("id"), (m.get("text") or "").strip()

    if cid_ == CHAT:
        for nu in m.get("new_chat_members", []):
            if nu["id"] in left:
                call("banChatMember", chat_id=CHAT, user_id=nu["id"])
                call("unbanChatMember", chat_id=CHAT, user_id=nu["id"], only_if_banned=True)
                call("sendMessage", chat_id=CHAT,
                     text=f"🔒 {nu.get('first_name','User')} left the group — re-entry costs $0.10. Pay via @CryptoBot to @lilko95, then DM @ref_rewards_support_bot with proof.")
        lm = m.get("left_chat_member")
        if lm and lm["id"] != OWNER:
            left.add(lm["id"])
        if text == "/claim":
            call("sendMessage", chat_id=CHAT, reply_to_message_id=m["message_id"],
                 text="📸 To claim the $2.50 USDT Ramp reward — DM @mini_reddit_referal_bot a screenshot of your completed signup (code 8P84M0 + KYC + top-up).")
        elif uid == OWNER and text.startswith("/paid"):
            import re
            mm = re.search(r"(\d{5,})", text)
            tgt = int(mm.group(1)) if mm else (m.get("reply_to_message", {}).get("from", {}) or {}).get("id")
            if tgt and tgt in left:
                left.discard(tgt)
                call("unbanChatMember", chat_id=CHAT, user_id=tgt, only_if_banned=True)
                call("sendMessage", chat_id=CHAT, text=f"✅ {tgt} unblocked — can rejoin.")
        elif uid == OWNER and text == "/gatestatus":
            call("sendMessage", chat_id=CHAT, text=f"left-blocked: {len(left)} | pending claims: {len(pending)} | paid: {len(done)}")
        continue

    # private DM
    if m["chat"].get("type") == "private":
        if uid == OWNER and text == "/claims":
            call("sendMessage", chat_id=OWNER, text=f"pending: {len(pending)} | paid: {len(done)}")
            continue
        if m.get("photo") or m.get("document"):
            if uid in done:
                call("sendMessage", chat_id=uid, text="✅ You already received your reward.")
                continue
            if uid in pending.values():
                call("sendMessage", chat_id=uid, text="⏳ Your proof is already under review.")
                continue
            claim_id = uuid.uuid4().hex[:8]
            pending[claim_id] = uid
            fid = (m.get("photo") or [{}])[-1].get("file_id") or (m.get("document") or {}).get("file_id")
            name = f"@{frm.get('username')}" if frm.get("username") else f"{frm.get('first_name')} (id {uid})"
            call("sendPhoto", chat_id=OWNER, photo=fid,
                 caption=f"💰 CLAIM {claim_id}\nFrom: {name}\nTask: Ramp signup (code 8P84M0)\nReward: $2.50 USDT",
                 reply_markup={"inline_keyboard": [[
                     {"text": "✅ Pay $2.50", "callback_data": f"pay:{claim_id}"},
                     {"text": "❌ Reject", "callback_data": f"rej:{claim_id}"}]]})
            call("sendMessage", chat_id=uid, text="✅ Proof received — under review. You'll be notified here.")
        else:
            call("sendMessage", chat_id=uid,
                 text="📸 Send a screenshot proving your completed Ramp signup (code 8P84M0 + KYC + top-up) to claim $2.50 USDT.")

st["left"], st["pending"], st["done"] = sorted(left), pending, sorted(done)
json.dump(st, open("state.json", "w"), indent=1)
print("processed", len(updates), "updates")
