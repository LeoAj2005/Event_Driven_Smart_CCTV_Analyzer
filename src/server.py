import os
import threading
import socket
import json
from flask import Flask, jsonify, request, render_template_string, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- GLOBAL SHARED STATE ---
system_state = {
    "status": "IDLE",  # IDLE, PROCESSING, DONE
    "logs": "Waiting for a video...",
    "queue": []
}
state_lock = threading.Lock()

# 🔥 NEW: Alert Queue for the Flutter App
unread_alerts = []
alerts_lock = threading.Lock()

UPLOAD_FOLDER = "/app/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# --- HTML TEMPLATES ---
HTML_INDEX = '''
<!DOCTYPE html>
<html>
<head>
    <title>AI Security System</title>
    <style>
        body { font-family: Arial; background: #f4f6f9; text-align: center; padding-top: 50px; }
        .card { background: white; border-radius: 10px; padding: 30px; display: inline-block; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
        button { background: #007bff; color: white; border: none; padding: 10px 20px; font-size: 16px; border-radius: 5px; cursor: pointer; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🚀 Upload Video for AI Analysis</h2>
        <form action="/upload" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept="video/*" required><br>
            <button type="submit">Process Video</button>
        </form>
    </div>
</body>
</html>
'''

HTML_PLAY = '''
<!DOCTYPE html>
<html>
<head>
    <title>Processing AI...</title>
    <style>
        body { background:#111; color:white; text-align:center; font-family: Arial; padding-top: 50px;}
        .container { max-width: 800px; margin: auto; }
        #loader { padding: 40px; border: 2px dashed #444; border-radius: 10px; }
        #log-text { color: #0f0; font-family: monospace; font-size: 18px; margin-top: 20px;}
        #player-container { display: none; }
        video { width: 100%; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
        .spinner { display: inline-block; width: 40px; height: 40px; border: 4px solid rgba(255,255,255,.3); border-radius: 50%; border-top-color: #fff; animation: spin 1s ease-in-out infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <div id="loader">
            <div class="spinner"></div>
            <h2>AI is Analyzing the Footage</h2>
            <div id="log-text">Initializing Engine...</div>
        </div>

        <div id="player-container">
            <h2>✅ Analysis Complete</h2>
            <video id="final-video" controls>
                <source src="/processed_video" type="video/mp4">
            </video>
            <br><br>
            <a href="/"><button style="padding:10px; cursor:pointer;">Analyze Another</button></a>
        </div>
    </div>

    <script>
        const loader = document.getElementById('loader');
        const player = document.getElementById('player-container');
        const logText = document.getElementById('log-text');
        const videoElement = document.getElementById('final-video');

        const interval = setInterval(() => {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    if (data.status === "PROCESSING") {
                        logText.innerText = data.logs;
                    } 
                    else if (data.status === "DONE") {
                        clearInterval(interval);
                        loader.style.display = "none";
                        player.style.display = "block";
                        
                        // 🔥 FIX: Add a timestamp to bypass browser cache!
                        videoElement.src = "/processed_video?t=" + new Date().getTime();
                        videoElement.load();
                        videoElement.play();
                    }
                });
        }, 1000);
    </script>
</body>
</html>
'''

# --- ROUTES (Web UI) ---
@app.route('/')
def index():
    return render_template_string(HTML_INDEX)

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file or file.filename == '':
        return "No file uploaded", 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    with state_lock:
        system_state["queue"].append(filepath)
        system_state["status"] = "PROCESSING"
        system_state["logs"] = f"Queued {filename} for analysis..."

    print(f"📥 File received and queued: {filepath}", flush=True)
    return render_template_string(HTML_PLAY)

@app.route('/api/status')
def status():
    with state_lock:
        return jsonify(system_state)

@app.route('/processed_video')
def processed_video():
    path = "/app/output/final_stream.mp4"
    if not os.path.exists(path):
        return "Video not ready", 404
    return send_file(path, mimetype="video/mp4")

# --- API ENDPOINTS FOR FLUTTER APP ---
@app.route('/api/upload', methods=['POST'])
def api_upload():
    """JSON endpoint for Flutter app to upload videos"""
    file = request.files.get('file')
    if not file or file.filename == '':
        return jsonify({"error": "No file uploaded"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    with state_lock:
        system_state["queue"].append(filepath)
        system_state["status"] = "PROCESSING"
        system_state["logs"] = f"Queued {filename} for analysis..."

    return jsonify({"success": True, "message": "Video queued for AI analysis"}), 200

@app.route('/api/logs', methods=['GET'])
def api_logs():
    """JSON endpoint to retrieve incident logs"""
    log_file = "/app/output/logs/incidents.jsonl"
    incidents = []
    
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            for line in f:
                try:
                    incidents.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
                    
    return jsonify({"incidents": incidents}), 200

@app.route('/api/alerts/poll', methods=['GET'])
def poll_alerts():
    """Flutter calls this every 2 seconds. It returns new alerts and clears the queue."""
    global unread_alerts
    with alerts_lock:
        # Copy current alerts and instantly clear the queue
        alerts_to_send = list(unread_alerts)
        unread_alerts.clear()
        
    return jsonify({"alerts": alerts_to_send}), 200

def run_server():
    ip = get_local_ip()
    print(f"\n🌐 Web UI Available at: http://{ip}:5000\n", flush=True)
    app.run(host='0.0.0.0', port=5000, threaded=True)

if __name__ == "__main__":
    run_server()