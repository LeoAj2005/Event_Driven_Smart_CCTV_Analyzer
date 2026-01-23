import json
import cv2
import time
import os
from collections import deque
from datetime import datetime
import numpy as np

class IncidentManager:
    def __init__(self, output_dir="/app/output"):
        self.log_dir = os.path.join(output_dir, "logs")
        self.clip_dir = os.path.join(output_dir, "clips")
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.clip_dir, exist_ok=True)
        
        # Buffer for pre-event context (last 100 frames)
        self.frame_buffer = deque(maxlen=100) 
        
        self.is_recording = False
        self.recording_frames_left = 0
        self.current_writer = None

    # ✅ FIXED: Renamed from 'update' to 'update_buffer' to match main.py
    def update_buffer(self, frame):
        """Adds frame to the pre-event buffer."""
        self.frame_buffer.append(frame)

    def log_event(self, event_type, obj_id, conf):
        """Logs event to JSONL file."""
        # ✅ FIXED: Convert numpy types to standard python types for JSON serialization
        safe_id = int(obj_id)
        safe_conf = float(conf)
        
        payload = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "object_id": safe_id,
            "confidence": safe_conf,
            "camera_id": "DROIDCAM-01"
        }
        
        # Save to file
        log_file = os.path.join(self.log_dir, "incidents.jsonl")
        with open(log_file, "a") as f:
            f.write(json.dumps(payload) + "\n")
            
        print(f"📝 Logged: {event_type} (ID: {safe_id})")
        return f"{int(time.time())}_{safe_id}"

    # ✅ REQUIRED: main.py calls this to save clips
    def trigger_clip_recording(self, incident_id, width, height, fps=25):
        """Starts recording a clip (Pre-event + Post-event)."""
        if self.is_recording:
            # If already recording, just extend the timer
            self.recording_frames_left = 150 # Add ~6 seconds
            return

        filename = os.path.join(self.clip_dir, f"clip_{incident_id}.mp4")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.current_writer = cv2.VideoWriter(filename, fourcc, fps, (width, height))
        
        # Write the past buffer (context) first
        for f in self.frame_buffer:
            self.current_writer.write(f)
            
        self.is_recording = True
        self.recording_frames_left = 150 # Record next 6 seconds
        print(f"🎬 Started Clip: {filename}")

    # ✅ REQUIRED: main.py calls this every loop
    def process_recording(self, frame):
        """Handles writing frames if recording is active."""
        if self.is_recording and self.current_writer:
            self.current_writer.write(frame)
            self.recording_frames_left -= 1
            
            if self.recording_frames_left <= 0:
                self.is_recording = False
                self.current_writer.release()
                self.current_writer = None
                print("⏹️ Clip Saved.")