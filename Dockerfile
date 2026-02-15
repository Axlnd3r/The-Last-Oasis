FROM python:3.11-slim

WORKDIR /app

# Install dependencies
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

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
