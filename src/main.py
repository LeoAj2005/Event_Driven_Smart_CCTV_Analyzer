import cv2
import supervision as sv
from ultralytics import YOLO
import os
import threading
import time
import subprocess
from datetime import datetime

from config import *
from engine import StateEngine
import server

gun_model = None
human_model = None

def process_video(filepath):
    print(f"\n🎯 AI Engine starting processing for: {filepath}", flush=True)
    
    cap = cv2.VideoCapture(filepath)
    if not cap.isOpened():
        print(f"❌ ERROR: Cannot open {filepath}", flush=True)
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

    brain = StateEngine((width, height))
    
    # Annotators for drawing on the video
    box_ann_human = sv.BoxAnnotator(thickness=2)
    box_ann_gun = sv.BoxAnnotator(thickness=4, color=sv.Color.RED)
    zone_ann = sv.PolygonZoneAnnotator(zone=brain.zone, color=sv.Color.RED, thickness=2)

    # Prepare output file (temporary, will be converted later)
    temp_output = "/app/output/temp_stream.mp4"
    os.makedirs("/app/output", exist_ok=True)
    
    # Use mp4v codec (OpenCV's default) – not web-friendly, but we'll convert
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_output, fourcc, fps, (width, height))

    frame_count = 0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        
        # Update Web UI Logs every 10 frames
        if frame_count % 10 == 0:
            log_msg = f"Scanning Frame {frame_count} / {total_frames}..."
            print(log_msg, flush=True)
            with server.state_lock:
                server.system_state["logs"] = log_msg

        # --- AI DETECTION ---
        # Human
        results_human = human_model.track(frame, persist=True, verbose=False, classes=[0], tracker=TRACKER_TYPE)
        dets_human = sv.Detections.from_ultralytics(results_human[0])

        # Gun
        dets_gun = sv.Detections.empty()
        if gun_model:
            results_gun = gun_model.track(frame, persist=True, verbose=False, conf=CONFIDENCE_THRESHOLD, tracker=TRACKER_TYPE)
            dets_gun = sv.Detections.from_ultralytics(results_gun[0])

        # --- EVENTS & ALERTS (NEW) ---
        # Only trigger events if we have gun detections (or combine with humans if needed)
        if dets_gun.tracker_id is not None:
            events = brain.update(dets_gun)  # brain.update expects gun detections for zone logic

            for e in events:
                event_type = e['type']
                
                # Check if this is a critical event that needs an alarm
                if any(keyword in event_type for keyword in ["Zone Violation", "FAST MOVEMENT", "Suspicious"]):
                    
                    alert_payload = {
                        "timestamp": datetime.now().isoformat(),
                        "event": event_type,
                        "object_id": int(e['id']),
                        "confidence": float(e['conf']),
                        "camera_id": "MAIN_GATE_CAM"
                    }
                    
                    # Push to the web server's queue for Flutter to grab
                    with server.alerts_lock:
                        server.unread_alerts.append(alert_payload)
                        
                    print(f"🚨 ALARM TRIGGERED: {event_type} (ID: {e['id']})", flush=True)

        # --- DRAW VISUALS ---
        frame = zone_ann.annotate(scene=frame)
        if len(dets_human) > 0:
            frame = box_ann_human.annotate(scene=frame, detections=dets_human)
        if len(dets_gun) > 0:
            frame = box_ann_gun.annotate(scene=frame, detections=dets_gun)

        out.write(frame)

    # Release resources
    cap.release()
    out.release()
    
    # -------------------------------
    # Convert to Web-Safe H.264 MP4
    # -------------------------------
    print("🎬 Converting to web-safe format for browser playback...", flush=True)
    
    final_path = "/app/output/final_stream.mp4"
    
    # FFmpeg conversion: re-encode to libx264
    subprocess.run([
        "ffmpeg", "-y", "-i", temp_output,
        "-vcodec", "libx264", "-preset", "fast",
        final_path
    ], check=True)
    
    # Clean up temporary file
    if os.path.exists(temp_output):
        os.remove(temp_output)
    
    print(f"✅ Video processing complete! Saved to {final_path}", flush=True)

    # Tell the Web UI we are finished
    with server.state_lock:
        server.system_state["status"] = "DONE"
        server.system_state["logs"] = "Analysis complete."

def main():
    global gun_model, human_model

    print("🚀 INITIALIZING AI PIPELINE...", flush=True)
    
    if os.path.exists(GUN_MODEL_PATH):
        gun_model = YOLO(GUN_MODEL_PATH)
        print("✅ Weapon model loaded", flush=True)
    else:
        gun_model = None
        print("⚠️ Weapon model missing", flush=True)

    human_model = YOLO(HUMAN_MODEL_PATH)
    print("✅ Human model loaded", flush=True)

    # Start Flask Web UI in the background
    threading.Thread(target=server.run_server, daemon=True).start()

    print("🟢 Engine ready. Waiting for uploads...", flush=True)

    # Main Engine Loop checking the queue
    while True:
        filepath_to_process = None
        
        with server.state_lock:
            if len(server.system_state["queue"]) > 0:
                filepath_to_process = server.system_state["queue"].pop(0)

        if filepath_to_process:
            process_video(filepath_to_process)
        else:
            time.sleep(1)

if __name__ == "__main__":
    main()