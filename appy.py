import os
import time
import threading
import requests
from urllib.parse import quote
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify

app = Flask(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_USERNAME = os.getenv("TELEGRAM_USERNAME", "")

IST = ZoneInfo("Asia/Kolkata")
REMINDERS = []

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        print("Telegram Send Error:", e)

def make_telegram_call(task_text):
    if not TELEGRAM_USERNAME:
        return
    user = TELEGRAM_USERNAME if TELEGRAM_USERNAME.startswith("@") else f"@{TELEGRAM_USERNAME}"
    msg = quote(f"Hello! Reminder for your task: {task_text}")
    url = f"http://api.callmebot.com/start.php?user={user}&text={msg}&lang=en-US-Standard-B&rpt=2"
    try:
        requests.get(url, timeout=15)
    except Exception as e:
        print("Call Error:", e)

def get_gemini_reply(user_message: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": user_message}]}],
        "systemInstruction": {
            "parts": [{"text": "You are a friendly personal assistant and task manager on Telegram. Keep answers concise and helpful."}]
        }
    }
    try:
        res = requests.post(url, json=payload, timeout=20)
        data = res.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print("Gemini Error:", e)
        return "Sorry, I faced a temporary error. Please try again!"

def reminder_loop():
    last_checked = ""
    while True:
        now_ist = datetime.now(IST).strftime("%H:%M")
        if now_ist != last_checked:
            last_checked = now_ist
            for r in REMINDERS[:]:
                if r["time"] == now_ist:
                    send_telegram_message(r["chat_id"], f"⏰ സമയം {now_ist} ആയി!\n👉 ടാസ്ക്: {r['task']}")
                    make_telegram_call(r["task"])
                    if not r.get("daily", False):
                        REMINDERS.remove(r)
        time.sleep(15)

threading.Thread(target=reminder_loop, daemon=True).start()

def handle_incoming(chat_id, user_text):
    text = user_text.strip()

    if text == "/start":
        welcome = (
            "👋 ഹലോ! ഞാൻ നിങ്ങളുടെ AI Task & Call Bot ആണ്.\n\n"
            "📌 ഒറ്റത്തവണ ഓർമ്മിപ്പിക്കാൻ:\n`/remind 18:30 Gym Workout`\n\n"
            "🔁 എല്ലാ ദിവസവും ഓർമ്മിപ്പിക്കാൻ:\n`/daily 06:30 Morning Walk`\n\n"
            "📋 ടാസ്കുകൾ കാണാൻ:\n`/tasks`\n\n"
            "മറ്റ് എന്ത് സംശയവും സാധാരണ പോലെ ചാറ്റിൽ ചോദിക്കാം!"
        )
        send_telegram_message(chat_id, welcome)
        return

    if text.startswith("/remind "):
        parts = text.split(" ", 2)
        if len(parts) >= 3:
            r_time, r_task = parts[1], parts[2]
            REMINDERS.append({"chat_id": chat_id, "time": r_time, "task": r_task, "daily": False})
            send_telegram_message(chat_id, f"✅ ടാസ്ക് സെറ്റ് ചെയ്തു!\n⏰ സമയം: {r_time}\n📝 ടാസ്ക്: {r_task}")
        else:
            send_telegram_message(chat_id, "ഇങ്ങനെ അയക്കുക:\n/remind 18:30 Workout")
        return

    if text.startswith("/daily "):
        parts = text.split(" ", 2)
        if len(parts) >= 3:
            r_time, r_task = parts[1], parts[2]
            REMINDERS.append({"chat_id": chat_id, "time": r_time, "task": r_task, "daily": True})
            send_telegram_message(chat_id, f"🔁 സ്ഥിരം ടാസ്ക് സെറ്റ് ചെയ്തു ({r_time}):\n📝 {r_task}")
        else:
            send_telegram_message(chat_id, "ഇങ്ങനെ അയക്കുക:\n/daily 06:30 Morning Walk")
        return

    if text == "/tasks":
        user_tasks = [r for r in REMINDERS if r["chat_id"] == chat_id]
        if not user_tasks:
            send_telegram_message(chat_id, "നിലവിൽ ടാസ്കുകൾ ഒന്നും സെറ്റ് ചെയ്തിട്ടില്ല.")
        else:
            msg = "📋 നിങ്ങളുടെ ടാസ്കുകൾ:\n"
            for i, r in enumerate(user_tasks, 1):
                dtype = "🔁 Daily" if r["daily"] else "⏳ Once"
                msg += f"{i}. {r['time']} - {r['task']} ({dtype})\n"
            send_telegram_message(chat_id, msg)
        return

    reply = get_gemini_reply(text)
    send_telegram_message(chat_id, reply)

@app.route("/", methods=["GET"])
def home():
    now_ist = datetime.now(IST).strftime("%H:%M:%S")
    return f"Telegram Bot is Live! Current IST: {now_ist}", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    try:
        if "message" in data and "text" in data["message"]:
            chat_id = data["message"]["chat"]["id"]
            user_text = data["message"]["text"]
            threading.Thread(target=handle_incoming, args=(chat_id, user_text)).start()
    except Exception as e:
        print("Webhook Error:", e)
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
