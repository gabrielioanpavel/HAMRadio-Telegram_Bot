FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    wget unzip curl gnupg chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "LOG_FILE=logs/$(date +%Y-%m-%d_%H-%M-%S).log ; python3 src/bot.py >> $LOG_FILE 2>&1 ; ls -1t logs/ | tail -n +10 | xargs -I {} rm -- logs/{}"]

