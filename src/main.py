import cv2
import supervision as sv
from ultralytics import YOLO
import os
import sys
import numpy as np

# Import our custom modules
from config import *
from engine import StateEngine
from incident import IncidentManager
import train # For auto-training check

def main():
    # --- 1. MODEL LOADING ---
    if not os.path.exists(MODEL_PATH):
        print(f"⚠️ Custom model not found at {MODEL_PATH}")
        print("🧠 Starting Automatic Training Sequence...")
        train.train_gun_model()
    
    print(f"🚀 STARTING SECURITY PIPELINE | Model: {MODEL_PATH}")
    model = YOLO(MODEL_PATH)
    
    # --- 2. SOURCE SELECTION ---
    if RTSP_URL and "192.168.X.X" not in RTSP_URL:
        print(f"📡 CONNECTING TO DROIDCAM: {RTSP_URL}")
        source = RTSP_URL
    else:
        print(f"📼 DroidCam not configured. LOADING VIDEO FILE: {FILE_VIDEO_PATH}")
        source = FILE_VIDEO_PATH

    cap = cv2.VideoCapture(source)
    
    # Check connection
    if not cap.isOpened():
        print("❌ CRITICAL ERROR: Could not open video source!")
        print(f"   Target: {source}")
        print("   Hint: If using DroidCam, ensure phone screen is ON and Laptop is on same Wi-Fi.")
        sys.exit(1)

    # Get Video Properties
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps    = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0 or np.isnan(fps): fps = 25.0 # Fallback for streams
    
    print(f"✅ Video Stream OK: {width}x{height} @ {fps} FPS")

    # --- 3. ENGINE INITIALIZATION ---
    brain = StateEngine((width, height))
    incident_manager = IncidentManager()
    
    # Visual Annotators
    box_annotator = sv.BoxAnnotator(thickness=2)
    label_annotator = sv.LabelAnnotator(text_scale=0.5, text_padding=5)
    trace_annotator = sv.TraceAnnotator(thickness=2, trace_length=30) # Shows movement path
    zone_annotator = sv.PolygonZoneAnnotator(zone=brain.zone, color=sv.Color.RED, thickness=2)
    
    # Output Debug Stream
    output_path = "/app/output/final_stream.mp4"
    out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))

    print("🎥 Pipeline Active. Press Ctrl+C to stop.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("⚠️ Video stream ended or lost connection.")
            break
        
        # Buffer frame for smart clips
        incident_manager.update_buffer(frame.copy())
        incident_manager.process_recording(frame)

        # --- A. DETECT & TRACK ---
        # Uses ByteTrack (from config.py) for high-speed tracking
        results = model.track(
            frame, 
            persist=True, 
            tracker=TRACKER_TYPE,
            verbose=False,
            conf=CONFIDENCE_THRESHOLD, 
            iou=IOU_THRESHOLD
        )
        detections = sv.Detections.from_ultralytics(results[0])

        # --- B. COGNITIVE ANALYSIS ---
        if detections.tracker_id is not None:
            
            # Analyze Behavior (Speed, Loitering, Zone)
            events = brain.update(detections)
            
            # Process Events
            for e in events:
                print(f"🔥 ALERT: {e['type']} (ID: {e['id']})")
                
                # 1. Log Event
                inc_id = incident_manager.log_event(e['type'], e['id'], e['conf'])
                
                # 2. Trigger Smart Clip Recording
                incident_manager.trigger_clip_recording(inc_id, width, height, fps)
                
                # 3. Flash Alert on Screen
                alert_color = (0, 0, 255) # Red
                if "FAST" in e['type']: alert_color = (0, 165, 255) # Orange for running
                
                cv2.putText(frame, f"{e['type']}!", (50, 100), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, alert_color, 3)

            # --- C. VISUALIZATION ---
            labels = [f"#{tracker_id}" for tracker_id in detections.tracker_id]
            
            # Draw Traces (Path), Boxes, Labels, and Zone
            frame = trace_annotator.annotate(frame, detections)
            frame = box_annotator.annotate(frame, detections)
            frame = label_annotator.annotate(frame, detections, labels=labels)
            frame = zone_annotator.annotate(frame)

        # Write to debug file
        out.write(frame)

    cap.release()
    out.release()
    print("🏁 Session Ended. Check /output/ folder for logs and clips.")

if __name__ == "__main__":
    main()