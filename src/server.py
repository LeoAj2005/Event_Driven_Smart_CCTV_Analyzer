import json
import os
import threading
import time
import cv2

from flask import Flask, Response, jsonify, request, render_template_string
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# -------------------------------
# SHARED DATA (MAIN ↔ SERVER)
# -------------------------------
video_frame = None
frame_lock = threading.Lock()

incident_log = []
new_incidents = []

# Queue for dynamic source switching
source_queue = []
source_queue_lock = threading.Lock()

# -------------------------------
# FILE UPLOAD CONFIG
# -------------------------------
UPLOAD_FOLDER = '/app/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ✅ DEBUG LOG (NEW)
print(f"📂 Upload folder: {UPLOAD_FOLDER}")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB


# -------------------------------
# HTML UI
# -------------------------------
HTML_TEMPLATE = '''
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
    <h3>📡 RTSP Stream</h3>
    <form action="/set_source" method="post">
        <input type="text" name="rtsp_url" placeholder="rtsp://..." size="50">
        <button type="submit">Start RTSP</button>
    </form>
</div>

<div class="card">
    <h3>📁 Upload Video</h3>
    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept="video/*">
        <button type="submit">Upload & Process</button>
    </form>
</div>

<div class="card">
    <h3>▶️ YouTube Video</h3>
    <form action="/set_source" method="post">
        <input type="text" name="youtube_url" placeholder="https://youtube.com/..." size="50">
        <button type="submit">Download & Process</button>
    </form>
</div>

<div class="card">
    <h3>📺 Live Feed</h3>
    <a href="/live" target="_blank">Open Stream</a>
</div>

<div class="card">
    <h3>📋 Incident Logs</h3>
    <a href="/logs" target="_blank">View Logs</a>
</div>

</body>
</html>
'''


# -------------------------------
# ROUTES
# -------------------------------
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/set_source', methods=['POST'])
def set_source():
    """Receive RTSP or YouTube URL from UI"""
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


@app.route('/upload', methods=['POST'])
def upload_file():
    """Upload local video file"""
    if 'file' not in request.files:
        return "❌ No file part", 400

    file = request.files['file']

    if file.filename == '':
        return "❌ No file selected", 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    try:
        file.save(filepath)
    except Exception as e:
        return f"❌ Upload failed: {str(e)}", 500

    # ✅ DEBUG LOG
    print(f"📥 Saved file to: {filepath}")

    source = f'file:{filepath}'

    with source_queue_lock:
        source_queue.append(source)

    return f"✅ Uploaded and queued: {filepath}"


@app.route('/logs')
def get_logs():
    """Return all stored incidents"""
    log_file = "/app/output/logs/incidents.jsonl"
    incidents = []

    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            for line in f:
                incidents.append(json.loads(line))

    return jsonify(incidents)


@app.route('/alerts')
def get_alerts():
    """Return new incidents (polling)"""
    global new_incidents

    with threading.Lock():
        alerts = new_incidents[:]
        new_incidents.clear()

    return jsonify(alerts)


@app.route('/live')
def live_feed():
    """Live MJPEG stream"""
    def generate():
        while True:
            with frame_lock:
                frame = video_frame

            if frame is not None:
                ret, jpeg = cv2.imencode('.jpg', frame)
                if ret:
                    yield (
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' +
                        jpeg.tobytes() +
                        b'\r\n'
                    )

            time.sleep(0.033)  # ~30 FPS

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


# -------------------------------
# SERVER RUNNER
# -------------------------------
def run_server():
    app.run(host='0.0.0.0', port=5000, threaded=True)