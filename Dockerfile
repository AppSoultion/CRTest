FROM python:3.9-slim

# 시스템 패키지 + Xvfb 설치
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    xvfb \
    x11vnc \
    fluxbox \
    ca-certificates \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99

EXPOSE 5000

# Xvfb와 앱을 함께 실행하는 스크립트 생성
RUN echo '#!/bin/bash\n\
Xvfb :99 -ac -screen 0 1280x1024x16 &\n\
export DISPLAY=:99\n\
sleep 2\n\
exec "$@"' > /app/start.sh \
&& chmod +x /app/start.sh

# 스크립트를 통해 앱 실행
CMD ["/app/start.sh", "gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "120", "app:app"]
