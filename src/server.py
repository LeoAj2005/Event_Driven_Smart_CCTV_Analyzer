import json
import os
import threading
import time
import cv2
import socket
from flask import Flask, Response, jsonify, request, render_template_string, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# --- SHARED MEMORY & STATE ---
video_frame = None
frame_lock = threading.Lock()

source_queue = []
source_queue_lock = threading.Lock()
new_incidents = []

# Tracks exactly what the AI is doing for the UI
system_state = {
    "status": "IDLE",
    "frame": 0,
    "message": "Waiting for video..."
}
system_state_lock = threading.Lock()  # for safe updates

UPLOAD_FOLDER = "/app/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    return ip

# --- HTML TEMPLATES ---
HTML_MAIN = '''
<!DOCTYPE html>
<html>
<head>
    <title>Security System Controller</title>
    <style>
        body { font-family: Arial; margin: 40px; background: #f4f6f9; }
        .card { background: white; border: 1px solid #ddd; padding: 20px; margin-bottom: 20px; border-radius: 10px; }
        input, button { padding: 10px; margin: 5px; }
        button { background: #007bff; color: white; border: none; cursor: pointer; border-radius: 5px; }
        button:hover { background: #0056b3; }
        h1 { color: #333; }
    </style>
</head>
<body>
    <h1>🚀 Security System Controller</h1>
    <div class="card">
        <h3>📁 Upload & Process Video</h3>
        <form action="/upload" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept="video/*">
            <button type="submit">Upload & Start AI</button>
        </form>
    </div>
    <div class="card">
        <h3>📊 Check Processing Status & Play</h3>
        <a href="/play" target="_blank"><button>Open Player / Tracker</button></a>
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_MAIN)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file", 400
    file = request.files['file']
    if file.filename == '':
        return "No file selected", 400

    filename = secure_filename(file.filename)
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    with source_queue_lock:
        source_queue.append(f'file:{path}')

    # Update state so the UI knows we queued a file
    with system_state_lock:
        system_state["status"] = "QUEUED"
        system_state["message"] = f"Queued: {filename}"

    return '''
    <script>
        window.location.href = "/play";
    </script>
    '''

# 🔥 CRITICAL: The UI needs this endpoint to get progress updates
@app.route('/status')
def get_status():
    with system_state_lock:
        return jsonify(system_state)

@app.route('/play')
def play_video():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Processing Tracker</title>
        <style>
            body { background:#111; color:white; text-align:center; font-family: Arial; padding-top: 50px;}
            #video-container { display: none; margin-top: 20px;}
            video { width: 100%; max-width: 800px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
            #logs { color: #0f0; font-family: monospace; margin-top: 20px; font-size: 18px;}
        </style>
    </head>
    <body>
      <h2 id="title">🔍 Checking AI Status...</h2>
      <div id="logs">Connecting to engine...</div>

      <div id="video-container">
          <video id="final-video" controls>
            <source src="/final_video_file" type="video/mp4">
          </video>
      </div>

      <script>
        const interval = setInterval(() => {
            fetch('/status')
                .then(res => res.json())
                .then(data => {
                    const title = document.getElementById('title');
                    const logs = document.getElementById('logs');
                    const videoContainer = document.getElementById('video-container');

                    if (data.status === "PROCESSING") {
                        title.innerText = "⚙️ AI is Analyzing Video...";
                        logs.innerText = "Processing Frame: " + data.frame;
                    }
                    else if (data.status === "DONE") {
                        title.innerText = "✅ Processing Complete!";
                        logs.innerText = "Video is ready.";
                        videoContainer.style.display = "block";
                        // Force video to reload to grab the newly finished file
                        document.getElementById('final-video').load();
                        clearInterval(interval);
                    }
                    else {
                        logs.innerText = data.message;
                    }
                })
                .catch(err => console.error("Error fetching status:", err));
        }, 1000);
      </script>
    </body>
    </html>
    '''

@app.route('/final_video_file')
def final_video_file():
    path = "/app/output/final_stream.mp4"
    if not os.path.exists(path):
        return "Video not found", 404
    return send_file(path, mimetype="video/mp4")

# 🔥 PREVENTS THE 500 ERROR: Safely checks if HLS files exist
@app.route('/hls/<path:filename>')
def hls_files(filename):
    filepath = os.path.join("/app/output", filename)
    if not os.path.exists(filepath):
        return "HLS stream not ready yet", 404
    return send_file(filepath)

# -------------------------------
# MJPEG Stream Endpoint (for live RTSP/YouTube)
# -------------------------------
def generate_frames():
    while True:
        with frame_lock:
            if video_frame is None:
                time.sleep(0.1)
                continue

            success, buffer = cv2.imencode('.jpg', video_frame)
            if not success:
                continue

        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.03)

@app.route('/video')
def video():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# -------------------------------
# Existing routes for RTSP/YouTube, logs, etc.
# -------------------------------
@app.route('/set_source', methods=['POST'])
def set_source():
    rtsp_url = request.form.get('rtsp_url')
    youtube_url = request.form.get('youtube_url')
    if rtsp_url:
        source = f'rtsp:{rtsp_url}'
    elif youtube_url:
        source = f'youtube:{youtube_url}'
    else:
        return "❌ No source provided", 400
    with source_queue_lock:
        source_queue.append(source)
    return f"✅ Source queued: {source}"

@app.route('/logs')
def get_logs():
    log_file = "/app/output/logs/incidents.jsonl"
    incidents = []
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            for line in f:
                incidents.append(json.loads(line))
    return jsonify(incidents)

def run_server():
    ip = get_local_ip()
    print(f"🌐 Server running at: http://{ip}:5000")
    print(f"➡️  Upload page: http://{ip}:5000")
    print(f"➡️  Status tracker: http://{ip}:5000/play")
    app.run(host='0.0.0.0', port=5000, threaded=True)

if __name__ == "__main__":
    run_server()