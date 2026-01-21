from roboflow import Roboflow
from ultralytics import YOLO
import os
from dotenv import load_dotenv

load_dotenv()

def train_gun_model():
    print("⬇️ Downloading Dataset from Roboflow...")
    api_key = os.getenv("ROBOFLOW_API_KEY")
    
    if not api_key:
        print("❌ ERROR: ROBOFLOW_API_KEY not found in .env file!")
        return

    rf = Roboflow(api_key=api_key)
    
    # 1. Download Dataset
    workspace = rf.workspace("workspace-1qko2")
    project = workspace.project("gun-detection-ghlzd")
    dataset = project.version(1).download("yolov8")

    print("🧠 Starting Model Training on GPU...")
    
    # 2. Load Base Model
    # We use v8n as the robust base for fine-tuning
    model = YOLO("yolov8n.pt") 
    
    # 3. Train
    results = model.train(
        data=f"{dataset.location}/data.yaml",
        epochs=20,               
        imgsz=640,
        batch=8,
        workers=2,
        project="/app/output/training_runs",
        name="yolo26_gun_custom" # We name our custom brain here
    )
    
    print(f"✅ Training Complete. Saved to: /app/output/training_runs/yolo26_gun_custom/weights/best.pt")

if __name__ == "__main__":
    train_gun_model()