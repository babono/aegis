# FastAPI backend image (used by docker-compose `web` profile and by Render).
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt

COPY . .

# Embedded graph backend by default: stateless per request, no DB to host.
ENV API_GRAPH_BACKEND=embedded
EXPOSE 8000

# Render provides $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
