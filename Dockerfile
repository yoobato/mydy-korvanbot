FROM python:3.12-slim
WORKDIR /app
COPY monitor.py boards.json ./
ENV PYTHONUNBUFFERED=1 STATE_PATH=/data/state.sqlite3
CMD ["python", "monitor.py"]
