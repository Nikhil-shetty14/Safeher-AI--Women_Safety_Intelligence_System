FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV MPLCONFIGDIR=/tmp/safeher_mpl

# Install OS audio and media libraries required by Whisper, Librosa, and ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency requirements
COPY requirements.txt .

# Install dependencies with pip
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY . .

# Create uploads and logs directories
RUN mkdir -p uploads logs /tmp/safeher_mpl

EXPOSE 8000

# Start Uvicorn serving ASGI socket_app (supports HTTP REST + Socket.IO)
CMD ["python", "run.py"]

