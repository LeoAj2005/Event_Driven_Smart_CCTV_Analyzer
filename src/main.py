import cv2
import supervision as sv
from ultralytics import YOLO
import os
import sys
import numpy as np
import threading
import time
from datetime import datetime

from config import *
from engine import StateEngine
from incident import IncidentManager

# 🔴 Flask server imports
from server import (
    run_server,
    video_frame,
    frame_lock,
    new_incidents,
    source_queue,
    source_queue_lock
)

# -------------------------------
# GLOBAL CONTROL
# -------------------------------
processing_thread = None
stop_processing = threading.Event()

gun_model = None
human_model = None


# -------------------------------
# YOUTUBE DOWNLOAD
# -------------------------------
def download_youtube(url):
    import yt_dlp
    print(f"⬇️ Downloading YouTube video: {url}")

    ydl_opts = {
        'format': 'best[height<=720]',
        'outtmpl': '/tmp/youtube_video.%(ext)s',
        'quiet': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


# -------------------------------
# PROCESS A SINGLE SOURCE
# -------------------------------
def process_source(source):
    global video_frame

    print(f"🎯 Starting processing for: {source}")

    # Parse source
    if source.startswith('rtsp:'):
        src = source[5:]
    elif source.startswith('youtube:'):
        src = download_youtube(source[8:])
    elif source.startswith('file:'):
        src = source[5:]
    else:
        src = source

    cap = cv2.VideoCapture(src)

    if not cap.isOpened():
        print(f"❌ Cannot open source: {src}")
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or fps > 120:
        fps = 25

    brain = StateEngine((width, height))
    incident_manager = IncidentManager()

    # --- Visualization ---
    box_ann_human = sv.BoxAnnotator(thickness=2, color=sv.ColorPalette.DEFAULT)
    lbl_ann_human = sv.LabelAnnotator(text_scale=0.5, color=sv.ColorPalette.DEFAULT)

    box_ann_gun = sv.BoxAnnotator(thickness=4, color=sv.Color.RED)
    lbl_ann_gun = sv.LabelAnnotator(text_scale=0.8, color=sv.Color.RED, text_color=sv.Color.WHITE)

    zone_ann = sv.PolygonZoneAnnotator(zone=brain.zone, color=sv.Color.RED, thickness=2)
    trace_ann = sv.TraceAnnotator(thickness=2, trace_length=30)

    out = cv2.VideoWriter(
        "/app/output/final_stream.mp4",
        cv2.VideoWriter_fourcc(*'mp4v'),
        fps,
        (width, height)
    )

    frame_count = 0

    # -------------------------------
    # PROCESS LOOP
    # -------------------------------
    while not stop_processing.is_set():
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        if frame_count % 30 == 0:
            print(f"✅ Processing Frame {frame_count}", flush=True)

        incident_manager.update_buffer(frame.copy())
        incident_manager.process_recording(frame)

        # --- HUMAN DETECTION ---
        results_human = human_model.track(
            frame, persist=True, verbose=False,
            classes=[0], tracker=TRACKER_TYPE
        )
        dets_human = sv.Detections.from_ultralytics(results_human[0])

        # --- GUN DETECTION ---
        dets_gun = sv.Detections.empty()
        if gun_model:
            results_gun = gun_model.track(
                frame, persist=True, verbose=False,
                conf=CONFIDENCE_THRESHOLD,
                tracker=TRACKER_TYPE
            )
            dets_gun = sv.Detections.from_ultralytics(results_gun[0])

        # --- EVENTS ---
        if dets_gun.tracker_id is not None:
            events = brain.update(dets_gun)

            for e in events:
                print(f"🔥 {e['type']} (ID: {e['id']})")

                incident_id = incident_manager.log_event(
                    e['type'], e['id'], e['conf']
                )

                incident_dict = {
                    "timestamp": datetime.now().isoformat(),
                    "event": e['type'],
                    "object_id": e['id'],
                    "confidence": e['conf'],
                    "camera_id": "MAIN_GATE_CAM"
                }

                new_incidents.append(incident_dict)

                incident_manager.trigger_clip_recording(
                    incident_id, width, height, fps
                )

                cv2.putText(
                    frame, f"ALERT: {e['type']}",
                    (50, 100), cv2.FONT_HERSHEY_SIMPLEX,
                    1.5, (0, 0, 255), 4
                )

        # --- DRAW ---
        if len(dets_human) > 0:
            if dets_human.tracker_id is not None:
                labels = [f"Person #{i}" for i in dets_human.tracker_id]
                frame = trace_ann.annotate(frame, dets_human)
            else:
                labels = [f"Person ({c:.2f})" for c in dets_human.confidence]

            frame = box_ann_human.annotate(frame, dets_human)
            frame = lbl_ann_human.annotate(frame, dets_human, labels=labels)

        if len(dets_gun) > 0:
            if dets_gun.tracker_id is not None:
                labels = [
                    f"WEAPON #{i} ({c:.2f})"
                    for i, c in zip(dets_gun.tracker_id, dets_gun.confidence)
                ]
            else:
                labels = [f"WEAPON ({c:.2f})" for c in dets_gun.confidence]

            frame = box_ann_gun.annotate(frame, dets_gun)
            frame = lbl_ann_gun.annotate(frame, dets_gun, labels=labels)

        frame = zone_ann.annotate(frame)

        # --- STREAM FRAME ---
        with frame_lock:
            video_frame = frame.copy()

        out.write(frame)

    cap.release()
    out.release()
    print(f"🛑 Stopped processing: {source}")


# -------------------------------
# MAIN ENTRY
# -------------------------------
def main():
    global processing_thread, gun_model, human_model

    print("🚀 INITIALIZING SYSTEM...")

    # Load models once
    if os.path.exists(GUN_MODEL_PATH):
        gun_model = YOLO(GUN_MODEL_PATH)
        print("✅ Weapon model loaded")
    else:
        gun_model = None
        print("⚠️ Weapon model missing")

    human_model = YOLO(HUMAN_MODEL_PATH)
    print("✅ Human model loaded")

    # Start server
    threading.Thread(target=run_server, daemon=True).start()
    print("🌐 Server running at http://0.0.0.0:5000")

    print("🟢 Waiting for source from web UI...")

    while True:
        with source_queue_lock:
            new_source = source_queue.pop(0) if source_queue else None

        if new_source:
            print(f"🔄 New source received: {new_source}")

            # Stop existing processing
            if processing_thread and processing_thread.is_alive():
                print("⏹ Stopping current stream...")
                stop_processing.set()
                processing_thread.join(timeout=5)
                stop_processing.clear()
                time.sleep(1)

            # Start new processing
            processing_thread = threading.Thread(
                target=process_source,
                args=(new_source,),
                daemon=True
            )
            processing_thread.start()

        else:
            time.sleep(1)


# -------------------------------
if __name__ == "__main__":
    main()