# Dockerfile - Chrome 설치 확실하게 
FROM python:3.9-slim

# 시스템 패키지 업데이트
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    xvfb \
    ca-certificates \
    apt-transport-https \
    software-properties-common

# Google Chrome 저장소 키 추가
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg

# Chrome 저장소 추가
RUN echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list

# 패키지 목록 업데이트 및 Chrome 설치
RUN apt-get update && apt-get install -y google-chrome-stable

# Chrome 설치 확인 및 심볼릭 링크 생성
RUN which google-chrome-stable || echo "Chrome not found after installation" \
    && ls -la /usr/bin/google-chrome* || echo "No chrome binaries found" \
    && google-chrome-stable --version || echo "Chrome version check failed"

# 작업 디렉토리 설정
WORKDIR /app

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 코드 복사
COPY . .

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/google-chrome-stable
ENV CHROME_PATH=/usr/bin/google-chrome-stable

# 포트 노출
EXPOSE 5000

# Xvfb와 앱을 함께 실행하는 스크립트 생성
RUN echo '#!/bin/bash\n\
echo "Starting Xvfb..."\n\
Xvfb :99 -ac -screen 0 1280x1024x16 &\n\
export DISPLAY=:99\n\
echo "Chrome path: $(which google-chrome-stable)"\n\
echo "Chrome version: $(google-chrome-stable --version 2>/dev/null || echo Failed)"\n\
sleep 3\n\
echo "Starting application..."\n\
exec "$@"' > /app/start.sh \
&& chmod +x /app/start.sh

# 스크립트를 통해 앱 실행
CMD ["/app/start.sh", "gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "120", "app:app"]

# 정리
RUN apt-get clean && rm -rf /var/lib/apt/lists/*
