FROM python:3.11-slim

# ✅ FIX: 'libgl1-mesa-glx' is deprecated. Replaced with 'libgl1' and 'libglib2.0-0'
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install AI Stack + Roboflow
RUN pip install --no-cache-dir \
    "ultralytics>=8.4.0" \
    roboflow \
    supervision==0.18.0 \
    opencv-python \
    numpy \
    python-dotenv

WORKDIR /app
CMD ["python", "src/main.py"]