FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY revoye_agent/ ./revoye_agent/
COPY autorun.py .

CMD ["python", "autorun.py"]
