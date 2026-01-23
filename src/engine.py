import time
import numpy as np
import supervision as sv
from config import *

class StateEngine:
    def __init__(self, frame_resolution_wh):
        self.objects = {} 
        # Create the Virtual Zone
        self.zone_polygon = (RESTRICTED_ZONE_POLYGON * np.array(frame_resolution_wh)).astype(int)
        self.zone = sv.PolygonZone(polygon=self.zone_polygon, frame_resolution_wh=frame_resolution_wh)

    def update(self, detections):
        current_time = time.time()
        events = []
        
        # Check if objects are inside the Restricted Zone
        is_in_zone = self.zone.trigger(detections=detections)
        
        # If no objects are tracked, return empty events
        if detections.tracker_id is None: 
            return events

        for i, (tracker_id, xyxy) in enumerate(zip(detections.tracker_id, detections.xyxy)):
            # Calculate Center Point of the Bounding Box
            center_x = (xyxy[0] + xyxy[2]) / 2
            center_y = (xyxy[1] + xyxy[3]) / 2
            center = (center_x, center_y)
            
            # --- 1. REGISTER / UPDATE OBJECT STATE ---
            if tracker_id not in self.objects:
                self.objects[tracker_id] = {
                    'start_time': current_time,
                    'positions': [center],
                    'events_triggered': set()
                }
            
            state = self.objects[tracker_id]
            state['positions'].append(center)
            
            # Keep history short (last 30 frames) to save memory
            if len(state['positions']) > 30: 
                state['positions'].pop(0)

            # --- 2. BEHAVIORAL CHECKS ---

            # 🛑 EVENT A: RESTRICTED ZONE ENTRY
            if is_in_zone[i]:
                if "zone" not in state['events_triggered']:
                    events.append({
                        "type": "🚫 Zone Violation", 
                        "id": tracker_id, 
                        "conf": detections.confidence[i]
                    })
                    state['events_triggered'].add("zone")

            # ⏱️ EVENT B: LOITERING (Time-Based)
            dwell_time = current_time - state['start_time']
            if dwell_time > LOITER_SECONDS:
                if "loiter" not in state['events_triggered']:
                    events.append({
                        "type": "👀 Suspicious Loitering", 
                        "id": tracker_id, 
                        "conf": detections.confidence[i]
                    })
                    state['events_triggered'].add("loiter")

            # 🏃 EVENT C: SUDDEN RUNNING (Speed-Based)
            # Compare current position to position 5 frames ago
            if len(state['positions']) > 5:
                pos_now = np.array(state['positions'][-1])
                pos_prev = np.array(state['positions'][-5])
                
                # Euclidean Distance (Pixels traveled in ~0.2 seconds)
                distance = np.linalg.norm(pos_now - pos_prev)
                
                if distance > SUSPICIOUS_SPEED_THRESHOLD:
                    # Note: We do NOT add to 'events_triggered' set because 
                    # running is continuous behavior, we want continuous alerts.
                    events.append({
                        "type": "⚠️ FAST MOVEMENT", 
                        "id": tracker_id, 
                        "conf": detections.confidence[i]
                    })

        return events