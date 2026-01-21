import json
import cv2
import time
import os
from collections import deque
from datetime import datetime

class IncidentManager:
    def __init__(self, output_dir="/app/output"):
        self.log_dir = os.path.join(output_dir, "logs")
        self.clip_dir = os.path.join(output_dir, "clips")
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.clip_dir, exist_ok=True)
        self.frame_buffer = deque(maxlen=100) # Pre-event buffer
        self.is_recording = False
        self.recording_frames = 0
        self.writer = None

    def update(self, frame):
        self.frame_buffer.append(frame)
        if self.is_recording and self.writer:
            self.writer.write(frame)
            self.recording_frames -= 1
            if self.recording_frames <= 0:
                self.is_recording = False
                self.writer.release()

    def log(self, event_type, obj_id, conf):
        # ✅ FIX: Convert numpy types to standard python types for JSON
        safe_id = int(obj_id)
        safe_conf = float(conf)
        
        payload = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "object_id": safe_id,      # Uses the clean 'int'
            "confidence": safe_conf    # Uses the clean 'float'
        }
        
        # Save to file
        with open(os.path.join(self.log_dir, "incidents.jsonl"), "a") as f:
            f.write(json.dumps(payload) + "\n")
            
        return f"{int(time.time())}_{safe_id}"

    def record_clip(self, filename_suffix, width, height, fps=25):
        if not self.is_recording:
            path = os.path.join(self.clip_dir, f"clip_{filename_suffix}.mp4")
            self.writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))
            for f in self.frame_buffer: self.writer.write(f)
            self.is_recording = True
            self.recording_frames = 150 # Record 6 seconds post-event