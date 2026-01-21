import numpy as np

# 📐 VIRTUAL ZONES (0.0 - 1.0 Normalized Coordinates)
# Example: A box covering the right 40% of the screen
RESTRICTED_ZONE_POLYGON = np.array([
    [0.6, 0.0], [1.0, 0.0], [1.0, 1.0], [0.6, 1.0]
])

# ⚙️ SYSTEM THRESHOLDS
CONFIDENCE_THRESHOLD = 0.4
IOU_THRESHOLD = 0.5
LOITER_SECONDS = 3.0       # Alert after 3 seconds
SPEED_THRESHOLD = 15.0     # Pixels/frame



#Tracker
TRACKER_TYPE = "bytetrack.yaml"

# 🕵️ CLASS IDS (Based on your Roboflow dataset)
# Your dataset has: 0=pistol (Check dataset.yaml after download to confirm)
WEAPON_CLASS_IDS = [0]     
PERSON_CLASS_ID = None     # This dataset might NOT have people. 
                           # If you need BOTH, you must merge datasets.