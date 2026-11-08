FROM python:3.12-slim

# Critical: Use wsproto==0.24.0 to avoid Render WebSocket crash
# See: https://github.com.com/encode/websockets/issues/811

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY services/ ./services/
COPY api/ ./api/
COPY frontend/ ./frontend/

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    ENVIRONMENT=production

# Expose the port
EXPOSE 8000

# Use wsproto for WebSocket (CRITICAL for Render compatibility)
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]