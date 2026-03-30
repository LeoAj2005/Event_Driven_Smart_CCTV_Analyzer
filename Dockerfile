FROM python:3.11-slim

# -------------------------------
# SYSTEM DEPENDENCIES
# -------------------------------
RUN apt-get update && apt-get install -y \
    # OpenCV + display fixes
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libxcb-xinerama0 \
    libxcb-shm0 \
    libxcb-xv0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-xfixes0 \
    libxcb-xkb1 \
    libxkbcommon-x11-0 \
    # Build tools (needed for some pip packages)
    gcc \
    # Tkinter (⚠️ may not work in headless Docker but included)
    tk-dev \
    python3-tk \
    # YouTube download support
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*


# -------------------------------
# PYTHON DEPENDENCIES
# -------------------------------
RUN pip install --no-cache-dir \
    "ultralytics>=8.4.0" \
    supervision==0.18.0 \
    roboflow \
    opencv-python \
    numpy \
    python-dotenv \
    flask \
    ffmpeg \
    flask-cors \
    pytz \
    yt-dlp


# -------------------------------
# WORKDIR + COPY
# -------------------------------
WORKDIR /app
COPY . /app


# -------------------------------
# RUN APP
# -------------------------------
CMD ["python", "src/main.py"]