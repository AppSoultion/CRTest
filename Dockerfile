# Dockerfile - 더 간단하고 안정적인 버전
FROM python:3.9

# 기본 패키지만 설치
RUN apt-get update && apt-get install -y \
    wget \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Chrome 직접 다운로드 및 설치
RUN wget -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y /tmp/chrome.deb || apt-get install -f -y \
    && rm /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/*

# Chrome 설치 확인
RUN google-chrome-stable --version

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99

EXPOSE 5000

# 시작 스크립트
RUN echo '#!/bin/bash\n\
Xvfb :99 -ac -screen 0 1280x1024x16 &\n\
export DISPLAY=:99\n\
sleep 2\n\
exec "$@"' > /start.sh && chmod +x /start.sh

CMD ["/start.sh", "gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
