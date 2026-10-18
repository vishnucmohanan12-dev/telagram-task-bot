import os
import time
import threading
import re
import requests
from datetime import datetime, timedelta
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
TELEGRAM_USERNAME = os.environ.get("TELEGRAM_USERNAME", "").strip()

tasks = []
worker_started = False
last_tick = "Not started"
lock = threading.Lock()

def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def normalize_time(time_str):
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
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        print(f"Send message error: {e}", flush=True)

def trigger_call_alert(task_name):
    if TELEGRAM_USERNAME:
        user = TELEGRAM_USERNAME.lstrip('@')
        try:
            msg = requests.utils.quote(f"Reminder for {task_name}")
            requests.get(f"http://api.callmebot.com/start.php?user=@{user}&text={msg}&lang=en-US-Standard-B", timeout=10)
        except Exception as e:
            print(f"Call error: {e}", flush=True)

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
        print(f"Gemini error: {e}", flush=True)
        return "Sorry, I faced a temporary error. Please try again!"

def reminder_worker():
    global last_tick
    print("Reminder worker thread started!", flush=True)
    while True:
        try:
            now_str = get_ist_now().strftime("%H:%M")
            last_tick = f"{now_str} (IST: {get_ist_now().strftime('%H:%M:%S')})"
            for t in tasks[:]:
                if t["time"] == now_str and t.get("last_sent") != now_str:
                    print(f"Triggering task: {t['task']} at {now_str}", flush=True)
                    send_telegram_message(t["chat_id"], f"⏰ റിമൈൻഡർ!\n📝 ടാസ്ക്: {t['task']}")
                    trigger_call_alert(t["task"])
                    t["last_sent"] = now_str
                    if not t["daily"]:
                        tasks.remove(t)
        except Exception as e:
            print(f"Worker loop error: {e}", flush=True)
        time.sleep(10)

def ensure_worker_running():
    global worker_started
    with lock:
        if not worker_started:
            t = threading.Thread(target=reminder_worker, daemon=True)
            t.start()
            worker_started = True

@app.route("/")
def home():
    ensure_worker_running()
    return f"Telegram Bot is Live! Current IST: {get_ist_now().strftime('%H:%M:%S')} | Worker Last Tick: {last_tick}"

@app.route("/webhook", methods=["POST"])
def webhook():
    ensure_worker_running()
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
            "👋 ഹലോ! ഞാൻ നിങ്ങളുടെ AI Task & Call Bot ആണ്.\n\n"
            "📌 ഒറ്റത്തവണ ഓർമ്മിപ്പിക്കാൻ:\n/remind 18:30 Gym Workout\n\n"
            "🔁 എല്ലാ ദിവസവും ഓർമ്മിപ്പിക്കാൻ:\n/daily 06:30 Morning Walk\n\n"
            "📋 ടാസ്കുകൾ കാണാൻ: /tasks\n"
            "🔍 സ്റ്റാറ്റസ് കാണാൻ: /status"
        )
        send_telegram_message(chat_id, welcome)

    elif cmd_lower == "/status":
        status_msg = (
            f"🟢 ബോട്ട് ആക്ടീവ് ആണ്!\n"
            f"🕒 ബോട്ട് സമയം (IST): {get_ist_now().strftime('%H:%M:%S')}\n"
            f"⚙️ ടൈമർ അവസാനം പ്രവർത്തിച്ചത്: {last_tick}\n"
            f"📋 ആകെ ടാസ്കുകൾ: {len(tasks)}"
        )
        send_telegram_message(chat_id, status_msg)

    elif cmd_lower == "/tasks":
        user_tasks = [t for t in tasks if t["chat_id"] == chat_id]
        if not user_tasks:
            send_telegram_message(chat_id, "📭 നിലവിൽ ടാസ്കുകൾ ഒന്നും സെറ്റ് ചെയ്തിട്ടില്ല.")
        else:
            msg_list = "📋 നിങ്ങളുടെ ടാസ്കുകൾ:\n\n"
            for i, t in enumerate(user_tasks, 1):
                dtype = "🔁 Daily" if t["daily"] else "📌 Once"
                msg_list += f"{i}. ⏰ {t['time']} - {t['task']} ({dtype})\n"
            send_telegram_message(chat_id, msg_list)

    elif cmd_lower.startswith(("/remind", "/remaind", "/daily")):
        is_daily = cmd_lower.startswith("/daily")
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
                send_telegram_message(chat_id, "⚠️ സമയം ശരിയായ രീതിയിൽ നൽകുക. ഉദാ: /remind 11:30 Tea")
        else:
            send_telegram_message(chat_id, "⚠️ ഫോർമാറ്റ് തെറ്റാണ്! ഇങ്ങനെ അയക്കുക:\n/remind 11:30 Tea shop")

    else:
        reply = ask_gemini(text)
        send_telegram_message(chat_id, reply)

    return "OK", 200

if __name__ == "__main__":
    ensure_worker_running()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
