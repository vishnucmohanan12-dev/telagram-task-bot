import os
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def ask_gemini(prompt):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": GEMINI_API_KEY
    }
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        res = requests.post(url, headers=headers, json=data, timeout=15)
        res_json = res.json()
        return res_json["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return "Sorry, I faced a temporary error. Please try again!"

HTML_APP = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Personal Tracker AI</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, sans-serif; }
        body { background: #0f172a; color: #f8fafc; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
        .header { background: #1e293b; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; }
        .header h1 { font-size: 18px; color: #38bdf8; display: flex; align-items: center; gap: 8px; }
        .clock { font-size: 14px; font-weight: bold; color: #94a3b8; background: #0f172a; padding: 6px 12px; border-radius: 20px; }
        .content { flex: 1; overflow-y: auto; padding: 16px; }
        .tab-view { display: none; height: 100%; flex-direction: column; }
        .tab-view.active { display: flex; }
        .card { background: #1e293b; padding: 16px; border-radius: 16px; margin-bottom: 16px; border: 1px solid #334155; }
        .input-group { margin-bottom: 12px; }
        .input-group label { display: block; font-size: 12px; color: #94a3b8; margin-bottom: 6px; }
        input[type="text"], input[type="time"] { width: 100%; padding: 12px; border-radius: 10px; border: 1px solid #475569; background: #0f172a; color: white; font-size: 15px; outline: none; }
        .row { display: flex; gap: 10px; align-items: center; }
        .btn { background: #0284c7; color: white; border: none; padding: 12px 18px; border-radius: 10px; font-weight: bold; width: 100%; cursor: pointer; font-size: 15px; }
        .task-item { background: #0f172a; padding: 12px 14px; border-radius: 12px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; border-left: 4px solid #38bdf8; }
        .task-info h4 { font-size: 15px; margin-bottom: 2px; }
        .task-info span { font-size: 12px; color: #94a3b8; }
        .del-btn { background: #ef4444; color: white; border: none; padding: 6px 10px; border-radius: 8px; font-size: 12px; cursor: pointer; }
        .chat-box { flex: 1; overflow-y: auto; padding-bottom: 12px; display: flex; flex-direction: column; gap: 10px; }
        .msg { max-width: 85%; padding: 10px 14px; border-radius: 14px; font-size: 14px; line-height: 1.4; word-wrap: break-word; }
        .msg.user { background: #0284c7; align-self: flex-end; border-bottom-right-radius: 2px; }
        .msg.bot { background: #1e293b; align-self: flex-start; border-bottom-left-radius: 2px; border: 1px solid #334155; }
        .chat-input-area { display: flex; gap: 8px; padding-top: 8px; }
        .nav { background: #1e293b; display: flex; border-top: 1px solid #334155; }
        .nav-btn { flex: 1; padding: 14px; text-align: center; color: #94a3b8; background: none; border: none; font-size: 14px; font-weight: bold; cursor: pointer; }
        .nav-btn.active { color: #38bdf8; border-top: 3px solid #38bdf8; background: #0f172a; }
        #callOverlay { display: none; position: fixed; inset: 0; background: rgba(15,23,42,0.97); z-index: 999; flex-direction: column; justify-content: center; align-items: center; padding: 24px; text-align: center; }
        .pulse { width: 100px; height: 100px; background: #0284c7; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-size: 42px; margin-bottom: 24px; animation: pulseAnim 1.2s infinite; }
        @keyframes pulseAnim { 0% { box-shadow: 0 0 0 0 rgba(56,189,248,0.7); } 70% { box-shadow: 0 0 0 25px rgba(56,189,248,0); } 100% { box-shadow: 0 0 0 0 rgba(56,189,248,0); } }
        .stop-btn { background: #ef4444; color: white; border: none; padding: 16px 40px; border-radius: 30px; font-size: 18px; font-weight: bold; margin-top: 35px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 Personal Tracker</h1>
        <div class="clock" id="clock">00:00:00</div>
    </div>

    <div class="content">
        <!-- TASKS TAB -->
        <div id="tasksTab" class="tab-view active">
            <div class="card">
                <div class="input-group">
                    <label>⏰ സമയം (Time)</label>
                    <input type="time" id="taskTime" required>
                </div>
                <div class="input-group">
                    <label>📝 ടാസ്ക് (Task Name)</label>
                    <input type="text" id="taskDesc" placeholder="ഉദാ: Gym Workout, Tea shop...">
                </div>
                <div class="input-group row">
                    <input type="checkbox" id="taskDaily" style="width:18px;height:18px;">
                    <label style="margin:0;color:#e2e8f0;font-size:14px;">🔁 എല്ലാ ദിവസവും (Daily Repeat)</label>
                </div>
                <button class="btn" onclick="addTask()">+ ടാസ്ക് സേവ് ചെയ്യുക</button>
            </div>

            <h3 style="font-size:15px;margin-bottom:10px;color:#94a3b8;">📋 നിങ്ങളുടെ ടാസ്കുകൾ</h3>
            <div id="taskList"></div>
        </div>

        <!-- GEMINI CHAT TAB -->
        <div id="chatTab" class="tab-view">
            <div class="chat-box" id="chatBox">
                <div class="msg bot">👋 ഹലോ വിഷ്ണു! എന്ത് സംശയവും എന്നോട് ചോദിക്കാം!</div>
            </div>
            <div class="chat-input-area">
                <input type="text" id="chatInput" placeholder="ചോദ്യം ടൈപ്പ് ചെയ്യുക..." onkeypress="if(event.key==='Enter')sendChat()">
                <button class="btn" style="width:auto;padding:0 20px;" onclick="sendChat()">➤</button>
            </div>
        </div>
    </div>

    <!-- CALL OVERLAY -->
    <div id="callOverlay">
        <div class="pulse">📞</div>
        <h2 style="color:#94a3b8;font-size:16px;margin-bottom:8px;">INCOMING VOICE REMINDER</h2>
        <h1 id="alertTaskName" style="font-size:28px;color:white;">Task Name</h1>
        <button class="stop-btn" onclick="stopAlarm()">🔕 Dismiss Call</button>
    </div>

    <!-- BOTTOM NAVIGATION -->
    <div class="nav">
        <button class="nav-btn active" onclick="switchTab('tasksTab', this)">⏰ Reminders</button>
        <button class="nav-btn" onclick="switchTab('chatTab', this)">💬 Gemini AI</button>
    </div>

    <script>
        let localTasks = JSON.parse(localStorage.getItem('tasks') || '[]');
        let alarmInterval = null;
        let audioCtx = null;

        function switchTab(id, btn) {
            document.querySelectorAll('.tab-view').forEach(e => e.classList.remove('active'));
            document.querySelectorAll('.nav-btn').forEach(e => e.classList.remove('active'));
            document.getElementById(id).classList.add('active');
            btn.classList.add('active');
        }

        function playBeep() {
            try {
                if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = 'sine';
                osc.frequency.setValueAtTime(880, audioCtx.currentTime);
                gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                osc.start();
                setTimeout(() => osc.stop(), 400);
            } catch(e) {}
        }

        function speakText(text) {
            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
                const u = new SpeechSynthesisUtterance("Hello Vishnu! Reminder for " + text);
                u.rate = 0.95;
                window.speechSynthesis.speak(u);
            }
        }

        function startAlarm(taskName) {
            document.getElementById('alertTaskName').innerText = taskName;
            document.getElementById('callOverlay').style.display = 'flex';
            playBeep();
            speakText(taskName);
            if (alarmInterval) clearInterval(alarmInterval);
            alarmInterval = setInterval(() => {
                playBeep();
                speakText(taskName);
            }, 4500);
        }

        function stopAlarm() {
            document.getElementById('callOverlay').style.display = 'none';
            if (alarmInterval) clearInterval(alarmInterval);
            if ('speechSynthesis' in window) window.speechSynthesis.cancel();
        }

        function renderTasks() {
            const list = document.getElementById('taskList');
            if (localTasks.length === 0) {
                list.innerHTML = '<div style="color:#64748b;text-align:center;padding:20px;">ടാസ്കുകൾ ഒന്നും ചേർത്തിട്ടില്ല.</div>';
                return;
            }
            list.innerHTML = localTasks.map((t, idx) => `
                <div class="task-item">
                    <div class="task-info">
                        <h4>⏰ ${t.time} - ${t.task}</h4>
                        <span>${t.daily ? '🔁 Daily' : '📌 Once'}</span>
                    </div>
                    <button class="del-btn" onclick="deleteTask(${idx})">Delete</button>
                </div>
            `).join('');
        }

        function addTask() {
            const timeVal = document.getElementById('taskTime').value;
            const descVal = document.getElementById('taskDesc').value.trim();
            const dailyVal = document.getElementById('taskDaily').checked;
            if (!timeVal || !descVal) return alert('സമയവും ടാസ്കും നൽകുക!');

            const newTask = { time: timeVal, task: descVal, daily: dailyVal, last_sent: '' };
            localTasks.push(newTask);
            localStorage.setItem('tasks', JSON.stringify(localTasks));
            document.getElementById('taskDesc').value = '';
            renderTasks();
        }

        function deleteTask(idx) {
            localTasks.splice(idx, 1);
            localStorage.setItem('tasks', JSON.stringify(localTasks));
            renderTasks();
        }

        async function sendChat() {
            const inp = document.getElementById('chatInput');
            const text = inp.value.trim();
            if (!text) return;
            const box = document.getElementById('chatBox');
            box.innerHTML += `<div class="msg user">${text}</div>`;
            inp.value = '';
            box.scrollTop = box.scrollHeight;

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({prompt: text})
                });
                const data = await res.json();
                box.innerHTML += `<div class="msg bot">${data.reply}</div>`;
                box.scrollTop = box.scrollHeight;
            } catch(e) {
                box.innerHTML += `<div class="msg bot">⚠️ നെറ്റ്‌വർക്ക് പ്രശ്നം, വീണ്ടും ശ്രമിക്കുക.</div>`;
            }
        }

        setInterval(() => {
            const now = new Date();
            const hrs = String(now.getHours()).padStart(2, '0');
            const mins = String(now.getMinutes()).padStart(2, '0');
            const secs = String(now.getSeconds()).padStart(2, '0');
            document.getElementById('clock').innerText = `${hrs}:${mins}:${secs}`;

            const curTime = `${hrs}:${mins}`;
            localTasks.forEach((t, i) => {
                if (t.time === curTime && t.last_sent !== curTime) {
                    t.last_sent = curTime;
                    startAlarm(t.task);
                    if (!t.daily) {
                        localTasks.splice(i, 1);
                    }
                    localStorage.setItem('tasks', JSON.stringify(localTasks));
                    renderTasks();
                }
            });
        }, 1000);

        renderTasks();
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_APP)

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    reply = ask_gemini(data.get("prompt", ""))
    return jsonify({"reply": reply})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
