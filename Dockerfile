FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU-only first (much smaller than GPU version)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install other dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY app/ ./app/
COPY agents/ ./agents/
COPY Assets/ ./Assets/
COPY run_agents.py ./

# Create data directory for SQLite
RUN mkdir -p /app/data

ENV DB_PATH=/app/data/last_oasis.sqlite3
ENV PORT=8000

EXPOSE $PORT

# Use shell form to allow environment variable expansion
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
