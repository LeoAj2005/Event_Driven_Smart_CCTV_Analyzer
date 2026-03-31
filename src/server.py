import os
import threading
import socket
import json
from flask import Flask, jsonify, request, render_template_string, send_file, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- GLOBAL SHARED STATE ---
system_state = {
    "status": "IDLE",  # IDLE, PROCESSING, DONE
    "logs": "Waiting for a video...",
    "queue": []
}
state_lock = threading.Lock()

# Alert Queue for the Flutter App
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

# ========== TERMINAL CLI DESIGN SYSTEM ==========
# Both HTML templates follow the design tokens:
# - Monospace font, deep black background, neon green foreground
# - No rounded corners, 1px solid/dashed borders
# - Bracket-style buttons with inverted video on hover
# - Blinking cursor, phosphor glow, scanline overlay
# - ASCII separators and prompt metaphors

HTML_INDEX = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
    <title>AI SECURITY SYSTEM :: TERMINAL</title>
    <style>
        /* ----- DESIGN TOKENS ----- */
        :root {
            --bg: #0a0a0a;
            --fg: #33ff00;
            --fg-dim: #1f521f;
            --fg-amber: #ffb000;
            --fg-error: #ff3333;
            --border: #1f521f;
            --glow: 0 0 5px rgba(51, 255, 0, 0.5);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            background: var(--bg);
            color: var(--fg);
            font-family: 'JetBrains Mono', 'Fira Code', 'VT323', monospace;
            font-size: 16px;
            line-height: 1.5;
            padding: 2rem 1rem;
            min-height: 100vh;
            position: relative;
        }

        /* CRT scanlines overlay */
        body::before {
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            background: repeating-linear-gradient(
                0deg,
                rgba(0, 0, 0, 0.1) 0px,
                rgba(0, 0, 0, 0.1) 2px,
                transparent 2px,
                transparent 6px
            );
            z-index: 999;
        }

        /* Container / Pane */
        .terminal-pane {
            max-width: 900px;
            margin: 0 auto;
            border: 1px solid var(--border);
            padding: 1.5rem;
            background: var(--bg);
            box-shadow: none;
        }

        /* ASCII Header - now plain text with prompt */
        .ascii-header {
            font-size: 1rem;
            line-height: 1.4;
            white-space: normal;
            margin-bottom: 1.5rem;
            color: var(--fg);
            text-shadow: var(--glow);
        }

        /* Titles */
        h1, h2, h3 {
            font-family: inherit;
            font-weight: normal;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin: 1rem 0;
            border-left: 3px solid var(--fg);
            padding-left: 0.75rem;
        }

        /* Buttons = bracket style */
        .terminal-btn {
            display: inline-block;
            background: transparent;
            color: var(--fg);
            border: 1px solid var(--fg);
            padding: 0.5rem 1.25rem;
            font-family: inherit;
            font-size: 1rem;
            text-transform: uppercase;
            cursor: pointer;
            transition: all 0.1s ease;
            text-decoration: none;
            margin: 0.5rem 0;
        }

        .terminal-btn:hover {
            background: var(--fg);
            color: var(--bg);
            text-shadow: none;
            border-color: var(--fg);
        }

        /* Form elements */
        .file-input-wrapper {
            margin: 1.5rem 0;
        }

        .file-label {
            display: inline-block;
            background: transparent;
            color: var(--fg);
            border: 1px solid var(--fg);
            padding: 0.5rem 1.25rem;
            font-family: inherit;
            font-size: 1rem;
            text-transform: uppercase;
            cursor: pointer;
        }

        .file-label:hover {
            background: var(--fg);
            color: var(--bg);
        }

        input[type="file"] {
            display: none;
        }

        .file-name {
            display: inline-block;
            margin-left: 1rem;
            font-size: 0.9rem;
            color: var(--fg-dim);
            word-break: break-all;
        }

        /* Prompt line */
        .prompt {
            margin: 1rem 0;
            font-size: 0.9rem;
        }

        .prompt-sign {
            color: var(--fg);
        }

        /* Separator */
        .separator {
            border: none;
            border-top: 1px dashed var(--border);
            margin: 1.5rem 0;
        }

        /* Footer */
        .footer {
            margin-top: 2rem;
            font-size: 0.8rem;
            color: var(--fg-dim);
            text-align: center;
            border-top: 1px solid var(--border);
            padding-top: 1rem;
        }

        /* Responsive */
        @media (max-width: 640px) {
            body {
                padding: 1rem;
            }
            .terminal-pane {
                padding: 1rem;
            }
            .ascii-header {
                font-size: 0.9rem;
            }
            .file-name {
                display: block;
                margin-left: 0;
                margin-top: 0.5rem;
            }
        }

        /* Blinking cursor effect for future use */
        @keyframes blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0; }
        }
        .blinking-cursor {
            display: inline-block;
            width: 10px;
            height: 1.2em;
            background-color: var(--fg);
            vertical-align: middle;
            animation: blink 1s step-end infinite;
            margin-left: 4px;
        }
    </style>
</head>
<body>
    <div class="terminal-pane">
        <!-- Replaced ASCII art with the requested title text, displayed as a terminal line -->
        <div class="ascii-header">
            <span class="prompt-sign">$></span> Intelligent Object Aware Event Modeling<br>
            <span style="display: inline-block; margin-left: 1.8rem;">for Smart Surveillance and Incident Management</span>
        </div>
        <h1>>_ AI SECURITY SYSTEM // UPLOAD SEQUENCE</h1>
        <div class="prompt">
            <span class="prompt-sign">user@acme:~$</span> ready for video payload
        </div>
        <form action="/upload" method="post" enctype="multipart/form-data">
            <div class="file-input-wrapper">
                <label class="file-label" for="video-file">[ BROWSE ]</label>
                <input type="file" name="file" id="video-file" accept="video/*" required>
                <span class="file-name" id="file-chosen">No file chosen</span>
            </div>
            <button type="submit" class="terminal-btn">[ INITIATE ANALYSIS ]</button>
        </form>
        <div class="separator"></div>
        <div class="footer">
            <span>[ SYSTEM READY ]</span> &nbsp;|&nbsp; 
            <span>USE [CTRL+C] TO ABORT</span> &nbsp;|&nbsp;
            <span>v1.0.0</span>
        </div>
    </div>

    <script>
        // Display selected filename in terminal style
        const fileInput = document.getElementById('video-file');
        const fileChosen = document.getElementById('file-chosen');
        fileInput.addEventListener('change', function() {
            if (fileInput.files.length > 0) {
                fileChosen.textContent = fileInput.files[0].name;
            } else {
                fileChosen.textContent = 'No file chosen';
            }
        });
    </script>
</body>
</html>
'''

HTML_PLAY = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
    <title>AI SECURITY SYSTEM :: PROCESSING</title>
    <style>
        /* Same design tokens as index */
        :root {
            --bg: #0a0a0a;
            --fg: #33ff00;
            --fg-dim: #1f521f;
            --fg-amber: #ffb000;
            --fg-error: #ff3333;
            --border: #1f521f;
            --glow: 0 0 5px rgba(51, 255, 0, 0.5);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            background: var(--bg);
            color: var(--fg);
            font-family: 'JetBrains Mono', 'Fira Code', 'VT323', monospace;
            font-size: 16px;
            line-height: 1.5;
            padding: 2rem 1rem;
            min-height: 100vh;
            position: relative;
        }

        body::before {
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            background: repeating-linear-gradient(
                0deg,
                rgba(0, 0, 0, 0.1) 0px,
                rgba(0, 0, 0, 0.1) 2px,
                transparent 2px,
                transparent 6px
            );
            z-index: 999;
        }

        .terminal-pane {
            max-width: 1000px;
            margin: 0 auto;
            border: 1px solid var(--border);
            padding: 1.5rem;
            background: var(--bg);
        }

        .ascii-header {
            font-size: 0.8rem;
            white-space: pre;
            margin-bottom: 1.5rem;
            color: var(--fg);
            text-shadow: var(--glow);
            text-align: center;
        }

        h2 {
            font-family: inherit;
            font-weight: normal;
            text-transform: uppercase;
            margin: 1rem 0;
            border-left: 3px solid var(--fg);
            padding-left: 0.75rem;
        }

        /* Log window */
        .log-window {
            border: 1px solid var(--border);
            background: #051005;
            padding: 1rem;
            margin: 1.5rem 0;
            font-family: inherit;
            font-size: 0.9rem;
            min-height: 200px;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .log-line {
            display: flex;
            flex-wrap: wrap;
            border-bottom: 1px dashed var(--fg-dim);
            padding: 0.25rem 0;
        }

        .log-prompt {
            color: var(--fg);
            margin-right: 0.75rem;
        }

        .log-message {
            color: var(--fg);
            flex: 1;
        }

        .cursor-line {
            display: flex;
            align-items: center;
        }
        .blinking-cursor {
            display: inline-block;
            width: 10px;
            height: 1.2em;
            background-color: var(--fg);
            vertical-align: middle;
            animation: blink 1s step-end infinite;
            margin-left: 6px;
        }
        @keyframes blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0; }
        }

        /* Video container */
        .video-pane {
            border: 1px solid var(--border);
            padding: 1rem;
            margin-top: 1.5rem;
        }
        .video-title {
            font-size: 0.8rem;
            text-transform: uppercase;
            color: var(--fg-dim);
            margin-bottom: 0.5rem;
        }
        video {
            width: 100%;
            background: black;
            border: 1px solid var(--fg-dim);
        }

        .terminal-btn {
            display: inline-block;
            background: transparent;
            color: var(--fg);
            border: 1px solid var(--fg);
            padding: 0.5rem 1.25rem;
            font-family: inherit;
            font-size: 1rem;
            text-transform: uppercase;
            cursor: pointer;
            text-decoration: none;
            margin-top: 1rem;
        }
        .terminal-btn:hover {
            background: var(--fg);
            color: var(--bg);
        }

        .separator {
            border-top: 1px dashed var(--border);
            margin: 1.5rem 0;
        }

        .footer {
            font-size: 0.8rem;
            color: var(--fg-dim);
            text-align: center;
            margin-top: 2rem;
        }

        @media (max-width: 640px) {
            body { padding: 1rem; }
            .terminal-pane { padding: 1rem; }
            .ascii-header { font-size: 0.6rem; white-space: normal; }
            .log-window { font-size: 0.8rem; }
        }
    </style>
</head>
<body>
    <div class="terminal-pane">
        <pre class="ascii-header">
   ____   ____   _   _   ____   _____   ____   _   _   __  __ 
  / ___| |  _ \\ | | | | |  _ \\ | ____| / ___| | | | | |  \\/  |
 | |     | |_) || |_| | | |_) ||  _|   \\___ \\ | |_| | | |\\/| |
 | |___  |  __/ |  _  | |  _ &lt; | |___   ___) ||  _  | | |  | |
  \\____| |_|    |_| |_| |_| \\_\\|_____| |____/ |_| |_| |_|  |_|
        </pre>
        <h2>>_ ANALYZING VIDEO STREAM</h2>
        <div class="log-window" id="log-window">
            <div class="log-line">
                <span class="log-prompt">$></span>
                <span class="log-message" id="log-text">Initializing neural engine...</span>
            </div>
            <div class="cursor-line">
                <span class="log-prompt">$_</span>
                <span class="blinking-cursor"></span>
            </div>
        </div>
        <div id="player-container" style="display: none;">
            <div class="video-pane">
                <div class="video-title">+--- PLAYBACK :: FINAL OUTPUT ---+</div>
                <video id="final-video" controls>
                    <source src="/processed_video" type="video/mp4">
                </video>
                <div style="text-align: center; margin-top: 1rem;">
                    <a href="/" class="terminal-btn">[ NEW ANALYSIS ]</a>
                </div>
            </div>
        </div>
        <div class="separator"></div>
        <div class="footer">
            <span>[ PROCESSING MODE ]</span> &nbsp;|&nbsp;
            <span>DO NOT CLOSE THIS PANEL</span>
        </div>
    </div>

    <script>
        const loaderDiv = document.getElementById('log-window');
        const playerDiv = document.getElementById('player-container');
        const logMessageSpan = document.getElementById('log-text');
        const videoElement = document.getElementById('final-video');

        // Helper: update log text and preserve terminal style
        function updateLog(message) {
            logMessageSpan.innerText = message;
        }

        // Poll status from backend
        const interval = setInterval(() => {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    if (data.status === "PROCESSING") {
                        updateLog(data.logs);
                    } 
                    else if (data.status === "DONE") {
                        clearInterval(interval);
                        // Hide the log area's cursor line and show video
                        const cursorLine = document.querySelector('.cursor-line');
                        if (cursorLine) cursorLine.style.display = 'none';
                        playerDiv.style.display = 'block';
                        // Force cache-bust for video
                        videoElement.src = "/processed_video?t=" + new Date().getTime();
                        videoElement.load();
                        videoElement.play().catch(e => console.log("Autoplay prevented:", e));
                    }
                })
                .catch(err => console.error("Polling error:", err));
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

@app.route('/static/final_stream.mp4')
def serve_final_video():
    output_directory = '/app/output'
    return send_from_directory(output_directory, 'final_stream.mp4')

# --- API ENDPOINTS FOR FLUTTER APP (unchanged) ---
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
        alerts_to_send = list(unread_alerts)
        unread_alerts.clear()
    return jsonify({"alerts": alerts_to_send}), 200

def run_server():
    ip = get_local_ip()
    print(f"\n🌐 Web UI Available at: http://{ip}:5000\n", flush=True)
    app.run(host='0.0.0.0', port=5000, threaded=True)

if __name__ == "__main__":
    run_server()