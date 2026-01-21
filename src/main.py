import cv2
import supervision as sv
from ultralytics import YOLO
import os
from config import *
from engine import StateEngine
from incident import IncidentManager
import train # Import our training module

# 📍 LOCATION OF YOUR TRAINED BRAIN
MODEL_PATH = "/app/output/training_runs/yolo26_gun_custom2/weights/best.pt"
VIDEO_PATH = "/app/data/test.mp4"
OUTPUT_PATH = "/app/output/final_stream.mp4"

def main():
    # 1. AUTO-TRAINING CHECK
    if not os.path.exists(MODEL_PATH):
        print("⚠️ No trained model found. Starting Automatic Training Sequence...")
        train.train_gun_model()
    
    print(f"🚀 STARTING PIPELINE with: {MODEL_PATH}")
    model = YOLO(MODEL_PATH)
    
    cap = cv2.VideoCapture(VIDEO_PATH)
    width, height = int(cap.get(3)), int(cap.get(4))
    fps = cap.get(5)
    
    # Engines
    brain = StateEngine((width, height))
    incident = IncidentManager()
    
    # Annotators
    box_ann = sv.BoxAnnotator(thickness=2)
    lbl_ann = sv.LabelAnnotator(text_scale=0.5)
    zone_ann = sv.PolygonZoneAnnotator(zone=brain.zone, color=sv.Color.RED)
    
    out = cv2.VideoWriter(OUTPUT_PATH, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        
        # Buffer for smart clips
        incident.update(frame.copy())

        # DETECT & TRACK
        # DETECT & TRACK
        # We now use the TRACKER_TYPE from config.py
        results = model.track(
            frame, 
            persist=True, 
            tracker=TRACKER_TYPE,  # <--- HERE IS THE SWITCH
            verbose=False, 
            conf=CONFIDENCE_THRESHOLD, 
            iou=IOU_THRESHOLD
        )
        detections = sv.Detections.from_ultralytics(results[0])

        if detections.tracker_id is not None:
            # COGNITIVE ENGINE
            events = brain.update(detections)
            
            for e in events:
                print(f"🔥 ALERT: {e['type']} (ID: {e['id']})")
                # Log & Record
                inc_id = incident.log(e['type'], e['id'], e['conf'])
                incident.record_clip(inc_id, width, height, fps)
                
                # Visual Alert
                cv2.putText(frame, f"ALERT: {e['type']}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)

            # VISUALIZE
            labels = [f"#{id} {model.names[cid]}" for id, cid in zip(detections.tracker_id, detections.class_id)]
            frame = box_ann.annotate(frame, detections)
            frame = lbl_ann.annotate(frame, detections, labels=labels)
            frame = zone_ann.annotate(frame)

        out.write(frame)

    cap.release()
    out.release()
    print("✅ Project Complete.")

if __name__ == "__main__":
    main()