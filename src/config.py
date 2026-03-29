import numpy as np
import os

# ===================================================
# 🎥 INPUT SOURCE CONFIGURATION
# ===================================================
RTSP_URL = None 
FILE_VIDEO_PATH = "/app/data/test.mp4"

# ===================================================
# 🧠 AI & DETECTION SETTINGS
# ===================================================
GUN_MODEL_PATH = "/app/output/training_runs/yolo26_gun_custom2/weights/best.pt"
HUMAN_MODEL_PATH = "yolov8n.pt"

# 🕵️ Tracker Selection
TRACKER_TYPE = "bytetrack.yaml"

# Detection Sensitivity
CONFIDENCE_THRESHOLD = 0.4  
IOU_THRESHOLD = 0.5         

# ===================================================
# 🚨 MODEL PATH DEBUG (CRITICAL FIX)
# ===================================================
print("🔍 Checking model path:", GUN_MODEL_PATH)
exists = os.path.exists(GUN_MODEL_PATH)
print("📁 Exists:", exists)

if not exists:
    print("❌ ERROR: Gun model not found!")
    
    # 🔁 Auto-suggest possible folders (VERY USEFUL)
    base_dir = "/app/output/training_runs"
    if os.path.exists(base_dir):
        print("📂 Available training runs:")
        for folder in os.listdir(base_dir):
            print("   -", folder)
    
    raise FileNotFoundError(
        f"Model not found at {GUN_MODEL_PATH}. Fix config.py path."
    )

# ===================================================
# 🚧 VIRTUAL SECURITY ZONES
# ===================================================
RESTRICTED_ZONE_POLYGON = np.array([
    [0.5, 0.0], [1.0, 0.0], [1.0, 1.0], [0.5, 1.0]
])

# ===================================================
# 🏃 BEHAVIORAL ANALYTICS RULES
# ===================================================
LOITER_SECONDS = 3.0       
SUSPICIOUS_SPEED_THRESHOLD = 25.0