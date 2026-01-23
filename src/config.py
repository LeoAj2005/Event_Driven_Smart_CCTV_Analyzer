# import numpy as np

# # 📐 VIRTUAL ZONES (0.0 - 1.0 Normalized Coordinates)
# # Example: A box covering the right 40% of the screen
# RESTRICTED_ZONE_POLYGON = np.array([
#     [0.6, 0.0], [1.0, 0.0], [1.0, 1.0], [0.6, 1.0]
# ])

# # ⚙️ SYSTEM THRESHOLDS
# CONFIDENCE_THRESHOLD = 0.4
# IOU_THRESHOLD = 0.5
# LOITER_SECONDS = 3.0       # Alert after 3 seconds
# SPEED_THRESHOLD = 15.0     # Pixels/frame



# #Tracker
# TRACKER_TYPE = "bytetrack.yaml"

# # 🕵️ CLASS IDS (Based on your Roboflow dataset)
# # Your dataset has: 0=pistol (Check dataset.yaml after download to confirm)
# WEAPON_CLASS_IDS = [0]     
# PERSON_CLASS_ID = None     # This dataset might NOT have people. 
#                            # If you need BOTH, you must merge datasets.

###########   RTSP Config


import numpy as np
import os

# ===================================================
# 🎥 INPUT SOURCE CONFIGURATION
# ===================================================
# ✅ DroidCam URL (HTTP MJPEG). 
# REPLACE '192.168.X.X' with the exact IP from your phone screen!
# Example: "http://192.168.1.5:4747/video"
RTSP_URL = "http://10.229.100.97:4747/video"  

# Fallback file if DroidCam fails (or if RTSP_URL is set to None)
FILE_VIDEO_PATH = "/app/data/test.mp4"


# ===================================================
# 🧠 AI & DETECTION SETTINGS
# ===================================================
# 🔫 Path to your Custom Trained Brain
MODEL_PATH = "/app/output/training_runs/yolo26_gun_custom2/weights/best.pt"

# 🕵️ Tracker Selection
# "bytetrack.yaml" -> Fastest, best for static CCTV (Recommended)
# "botsort.yaml"   -> Better for moving cameras, but slower
TRACKER_TYPE = "bytetrack.yaml"

# Detection Sensitivity
CONFIDENCE_THRESHOLD = 0.4  # Only trust detections > 40% confident
IOU_THRESHOLD = 0.5         # Overlap threshold for tracking


# ===================================================
# 🚧 VIRTUAL SECURITY ZONES
# ===================================================
# Define a polygon (0.0 - 1.0 relative coordinates)
# Current: A box covering the RIGHT HALF of the screen
RESTRICTED_ZONE_POLYGON = np.array([
    [0.5, 0.0], [1.0, 0.0], [1.0, 1.0], [0.5, 1.0]
])


# ===================================================
# 🏃 BEHAVIORAL ANALYTICS RULES
# ===================================================
# ⏱️ Loitering: Trigger if gun stays in scene > 3 seconds
LOITER_SECONDS = 3.0       

# 💨 Running: Trigger if object moves > 25 pixels in 5 frames
# Adjust this number based on your camera resolution
SUSPICIOUS_SPEED_THRESHOLD = 25.0