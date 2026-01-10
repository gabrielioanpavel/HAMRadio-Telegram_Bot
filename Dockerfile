FROM python:3.11-slim

# Disable Python output buffering for real-time logging
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    wget unzip curl gnupg chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "python3 src/bot.py 2>&1 | tee logs/$(date +%Y-%m-%d_%H-%M-%S).log"]

