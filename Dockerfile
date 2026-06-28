FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default command produces Firm A's report. docker-compose overrides this to
# run both firms in sequence. The entrypoint waits for Neo4j to be reachable.
CMD ["python", "run.py", "--firm", "A"]
