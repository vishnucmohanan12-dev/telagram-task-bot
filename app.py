import os
import time
import threading
import re
import requests
from datetime import datetime, timedelta
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
TELEGRAM_USERNAME = os.environ.get("TELEGRAM_USERNAME", "")

tasks = []

def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def normalize_time(time_str):
    # Converts formats like 9.38pm, 5.30am, 21:30 into standard HH:MM (24-hr)
    s = time_str.strip().lower().replace('.', ':')
    m = re.match(r'^(\d{1,2}):(\d{2})\s*(am|pm)?$', s)
    if not m:
        return None
    hr, mn, period = int(m.group(1)), int(m.group(2)), m.group(3)
    if period == 'pm' and hr < 12:
        hr += 12
    elif period == 'am' and hr == 12:
        hr = 0
    return f"{hr:02d}:{mn:02d}"

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def trigger_call_alert():
    if TELEGRAM_USERNAME:
        user = TELEGRAM_USERNAME.lstrip('@')
        try:
            requests.get(f"http://api.callmebot.com/start.php?user=@{user}&text=Task+Reminder+Alert&lang=en-US-Standard-B", timeout=10)
        except Exception:
            pass

def ask_gemini(prompt):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": GEMINI_API_KEY
    }
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    try:
        res = requests.post(url, headers=headers, json=data, timeout=15)
        res_json = res.json()
        return res_json["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return "Sorry, I faced a temporary error. Please try again!"

def reminder_worker():
    while True:
        now_str = get_ist_now().strftime("%H:%M")
        for t in tasks[:]:
            if t["time"] == now_str and t.get("last_sent") != now_str:
                send_telegram_message(t["chat_id"], f"⏰ *Reminder!* \n📝 {t['task']}")
                trigger_call_alert()
                t["last_sent"] = now_str
                if not t["daily"]:
                    tasks.remove(t)
        time.sleep(15)

threading.Thread(target=reminder_worker, daemon=True).start()

@app.route("/")
def home():
    return f"Telegram Bot is Live! Current IST: {get_ist_now().strftime('%H:%M:%S')}"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return "OK", 200

    msg = data["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()
    if not text:
        return "OK", 200

    cmd_lower = text.lower()

    if cmd_lower == "/start":
        welcome = (
            "👋 ഹലോ! ഞാൻ നിങ്ങളുടെ WARUNNI ആണ്.\n\n"
            "📌 ഒറ്റത്തവണ ഓർമ്മിപ്പിക്കാൻ:\n`/remind 18:30 Gym Workout` അല്ലെങ്കിൽ `/remind 6.30pm Gym`\n\n"
            "🔁 എല്ലാ ദിവസവും ഓർമ്മിപ്പിക്കാൻ:\n`/daily 06:30 Morning Walk`\n\n"
            "📋 ടാസ്കുകൾ കാണാൻ:\n`/tasks`\n\n"
            "മറ്റ് എന്ത് സംശയവും സാധാരണ പോലെ ചാറ്റിൽ ചോദിക്കാം!"
        )
        send_telegram_message(chat_id, welcome)

    elif cmd_lower == "/tasks":
        user_tasks = [t for t in tasks if t["chat_id"] == chat_id]
        if not user_tasks:
            send_telegram_message(chat_id, "📭 നിലവിൽ ടാസ്കുകൾ ഒന്നും സെറ്റ് ചെയ്തിട്ടില്ല.")
        else:
            msg_list = "📋 *നിങ്ങളുടെ ടാസ്കുകൾ:*\n\n"
            for i, t in enumerate(user_tasks, 1):
                dtype = "🔁 Daily" if t["daily"] else "📌 Once"
                msg_list += f"{i}. ⏰ {t['time']} - {t['task']} ({dtype})\n"
            send_telegram_message(chat_id, msg_list)

    elif cmd_lower.startswith(("/remind", "/remaind", "/daily")):
        is_daily = cmd_lower.startswith("/daily")
        # Matches time like 9.36 pm, 9.36pm, 21:36
        match = re.match(r'^/\w+\s+(\d{1,2}[:.]\d{2}\s*(?:am|pm)?)\s+(.+)$', text, re.IGNORECASE)
        if match:
            raw_time, task_desc = match.group(1), match.group(2)
            norm_time = normalize_time(raw_time)
            if norm_time:
                tasks.append({
                    "chat_id": chat_id,
                    "time": norm_time,
                    "task": task_desc,
                    "daily": is_daily,
                    "last_sent": ""
                })
                if is_daily:
                    send_telegram_message(chat_id, f"🔁 സ്ഥിരം ടാസ്ക് സെറ്റ് ചെയ്തു!\n⏰ സമയം: {norm_time} ({raw_time})\n📝 ടാസ്ക്: {task_desc}")
                else:
                    send_telegram_message(chat_id, f"✅ ടാസ്ക് സെറ്റ് ചെയ്തു!\n⏰ സമയം: {norm_time} ({raw_time})\n📝 ടാസ്ക്: {task_desc}")
            else:
                send_telegram_message(chat_id, "⚠️ സമയം ശരിയായ രീതിയിൽ നൽകുക. ഉദാഹരണത്തിന്: `/remind 9.45pm Tea`")
        else:
            send_telegram_message(chat_id, "⚠️ ഫോർമാറ്റ് തെറ്റാണ്! ഇങ്ങനെ അയക്കുക:\n`/remind 9.45pm Tea shop`")

    else:
        reply = ask_gemini(text)
        send_telegram_message(chat_id, reply)

    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

