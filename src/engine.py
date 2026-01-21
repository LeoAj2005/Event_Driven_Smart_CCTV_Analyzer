import time
import numpy as np
import supervision as sv
from config import *

class StateEngine:
    def __init__(self, frame_resolution_wh):
        self.objects = {} 
        self.zone_polygon = (RESTRICTED_ZONE_POLYGON * np.array(frame_resolution_wh)).astype(int)
        self.zone = sv.PolygonZone(polygon=self.zone_polygon, frame_resolution_wh=frame_resolution_wh)

    def update(self, detections):
        current_time = time.time()
        events = []
        
        is_in_zone = self.zone.trigger(detections=detections)
        
        if detections.tracker_id is None: return events

        for i, (tracker_id, xyxy) in enumerate(zip(detections.tracker_id, detections.xyxy)):
            center = ((xyxy[0] + xyxy[2]) / 2, (xyxy[1] + xyxy[3]) / 2)
            
            # 1. State Management
            if tracker_id not in self.objects:
                self.objects[tracker_id] = {
                    'start_time': current_time,
                    'positions': [center],
                    'events_triggered': set()
                }
            
            state = self.objects[tracker_id]
            state['positions'].append(center)
            if len(state['positions']) > 20: state['positions'].pop(0)

            # 🛑 EVENT: RESTRICTED ZONE
            if is_in_zone[i]:
                if "zone" not in state['events_triggered']:
                    events.append({"type": "Zone Violation", "id": tracker_id, "conf": detections.confidence[i]})
                    state['events_triggered'].add("zone")

            # ⏱️ EVENT: LOITERING
            dwell = current_time - state['start_time']
            if dwell > LOITER_SECONDS:
                if "loiter" not in state['events_triggered']:
                    events.append({"type": "Weapon Loitering", "id": tracker_id, "conf": detections.confidence[i]})
                    state['events_triggered'].add("loiter")

        return events