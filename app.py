# app.py - 원본 Python 코드와 동일한 로직으로 수정
from flask import Flask, request, jsonify, Response
import requests
import re
import time
import random
import logging
import os
import tempfile
import shutil
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc

app = Flask(__name__)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def resolve_short_url(short_url):
    """단축 URL 해결 메서드"""
    logger.info(f"단축 URL 해결 시도: {short_url}")
    try:
        response = requests.head(short_url, allow_redirects=False)
        if 300 <= response.status_code < 400:
            redirect_url = response.headers.get('Location')
            if redirect_url and "coupang.com" in redirect_url:
                logger.info(f"단축 URL 리다이렉트 발견: {redirect_url}")
                return redirect_url
            else:
                logger.error(f"유효하지 않은 쿠팡 URL로 리다이렉트됨: {redirect_url}")
        else:
            logger.error(f"단축 URL 해결 실패: {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"단축 URL 해결 중 오류: {str(e)}")
        return None

def process_product_url(url):
    """쿠팡 상품 URL 처리 및 모바일 버전으로 변환"""
    if "coupang.com" not in url:
        return None
    
    # URL을 모바일 버전으로 변환 (성능 및 파싱 용이성 개선)
    if "www.coupang.com" in url:
        url = url.replace("www.coupang.com", "m.coupang.com")
    if "/vp/products/" in url:
        url = url.replace("/vp/products/", "/vm/products/")
    
    logger.info(f"처리된 URL: {url}")
    return url

def extract_product_info_with_undetected(product_url, proxy=None):
    """undetected-chromedriver를 사용하여 상품 정보 추출 (원본 코드와 동일)"""
    driver = None
    try:
        logger.info(f"undetected-chromedriver를 사용하여 상품 정보 추출 시도: {product_url}")

        # undetected_chromedriver 설정
        try:
            # 환경 변수 설정 (캐시 문제 해결)
            temp_dir = os.path.join(os.path.expanduser('~'), '.temp_chromedriver')
            os.makedirs(temp_dir, exist_ok=True)
            os.environ['UC_DRIVER_CACHE_DIR'] = temp_dir

            # undetected_chromedriver 캐시 재설정 옵션
            if not hasattr(uc, 'TARGET_VERSION'):
                uc.TARGET_VERSION = 114  # 고정 버전 설정

            # 다운로드 시간 초과 시간 증가
            try:
                import socket
                socket.setdefaulttimeout(30)  # 기본 시간 초과 설정 (초)
            except:
                pass

        except Exception as e:
            logger.error(f"undetected_chromedriver 설정 오류: {str(e)}")

        # Chrome 옵션 설정 (원본과 동일)
        options = uc.ChromeOptions()
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--lang=ko-KR,ko")

        # 메모리 관련 설정 추가
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-setuid-sandbox")

        # 성능 개선을 위한 추가 설정
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")
        options.add_argument("--dns-prefetch-disable")
        options.add_argument("--disable-web-security")

        # 이미지 로딩 비활성화 (성능 향상)
        options.add_argument("--blink-settings=imagesEnabled=false")
        
        # 헤드리스 모드 (서버 환경에서)
        options.add_argument("--headless")

        # 프록시 설정
        if proxy:
            options.add_argument(f'--proxy-server={proxy}')
            logger.info(f"프록시 설정: {proxy}")

        # 브라우저 시작 (다운로드 오류 처리 추가)
        try:
            driver = uc.Chrome(options=options, use_subprocess=True)
            driver.set_page_load_timeout(30)
        except Exception as e:
            logger.error(f"Chrome 드라이버 초기화 오류: {str(e)}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")

            # 오류가 ContentTooShortError 또는 다운로드 관련 오류인 경우 캐시 정리 시도
            error_msg = str(e).lower()
            if "content" in error_msg or "download" in error_msg or "urlretrieve" in error_msg:
                logger.info("ChromeDriver 다운로드 오류 감지, 캐시 정리 시도...")
                try:
                    cache_dir = os.path.join(os.path.expanduser('~'), '.undetected_chromedriver')
                    if os.path.exists(cache_dir):
                        shutil.rmtree(cache_dir)
                        logger.info(f"캐시 디렉토리 삭제 성공: {cache_dir}")

                    temp_dir = os.path.join(os.path.expanduser('~'), '.temp_chromedriver')
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                        logger.info(f"임시 캐시 디렉토리 삭제 성공: {temp_dir}")
                except Exception as cache_err:
                    logger.error(f"캐시 정리 오류: {str(cache_err)}")

            return None  # 초기화 실패 시 None 반환

        try:
            # 쿠팡 홈페이지 먼저 방문
            logger.info("쿠팡 홈페이지 사전 방문...")
            driver.get("https://m.coupang.com")
            time.sleep(3)

            # 상품 페이지 방문
            logger.info(f"상품 페이지 방문: {product_url}")
            driver.get(product_url)
            time.sleep(5)  # 충분한 로딩 시간 부여

            # 페이지 로드 대기
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except TimeoutException:
                logger.warning("페이지 로드 타임아웃")
                if driver:
                    driver.quit()
                return None
            except Exception as wait_err:
                logger.warning(f"대기 중 오류: {str(wait_err)}")
                # 계속 진행 시도

            # HTML 반환
            html_content = driver.page_source
            logger.info(f"HTML 추출 완료 ({len(html_content)} bytes)")
            
            return html_content

        finally:
            # 브라우저 종료 - 여러 방법으로 시도
            if driver:
                try:
                    # 1. 일반적인 종료 시도
                    driver.quit()
                    logger.info("크롬 브라우저가 정상적으로 종료되었습니다.")
                except Exception as e:
                    logger.warning(f"일반 종료 실패: {str(e)}, 강제 종료 시도 중...")
                    try:
                        # 2. 창 닫기 시도
                        driver.close()
                        logger.info("창 닫기 성공")
                    except:
                        pass

                    try:
                        # 3. 다시 quit 시도
                        driver.quit()
                        logger.info("두 번째 종료 시도 성공")
                    except:
                        pass

    except Exception as e:
        logger.error(f"undetected-chromedriver 사용 중 오류 발생: {str(e)}")
        # 자세한 오류 정보 로깅
        import traceback
        logger.error(f"상세 오류: {traceback.format_exc()}")

        # 브라우저 강제 종료 시도 (추가된 부분)
        if driver:
            try:
                driver.quit()
            except:
                pass

        return None

def extract_product_info(product_url, max_retries=3, proxy=None):
    """상품 정보 추출 (메인 함수) - 원본과 동일한 로직"""
    
    # URL 처리
    if "link.coupang.com" in product_url:
        logger.info(f"단축 URL 감지됨: {product_url}")
        resolved_url = resolve_short_url(product_url)
        if resolved_url:
            product_url = resolved_url
        else:
            logger.error(f"단축 URL을 해결할 수 없습니다: {product_url}")
            return None

    # URL 모바일 버전으로 변환
    product_url = process_product_url(product_url)
    if not product_url:
        logger.error("유효한 쿠팡 URL이 아닙니다")
        return None

    # undetected_chromedriver 경로 확인 및 생성
    try:
        # undetected_chromedriver 캐시 디렉토리 경로
        cache_dir = os.path.join(os.path.expanduser('~'), '.undetected_chromedriver')

        # 캐시 디렉토리가 없거나 문제가 있으면 재생성
        if not os.path.exists(cache_dir) or not os.access(cache_dir, os.W_OK):
            logger.info("undetected_chromedriver 캐시 디렉토리 재설정 중...")
            if os.path.exists(cache_dir):
                try:
                    shutil.rmtree(cache_dir)
                except:
                    pass
            try:
                os.makedirs(cache_dir, exist_ok=True)
            except:
                # 기본 디렉토리에 문제가 있으면 임시 디렉토리로 설정
                temp_dir = tempfile.gettempdir()
                cache_dir = os.path.join(temp_dir, '.undetected_chromedriver')
                os.makedirs(cache_dir, exist_ok=True)
                logger.info(f"undetected_chromedriver 캐시 디렉토리를 임시 경로로 설정: {cache_dir}")

                # 환경 변수로 설정
                os.environ['UC_DRIVER_CACHE_DIR'] = cache_dir
    except Exception as e:
        logger.warning(f"캐시 디렉토리 설정 중 오류: {str(e)}, 기본값 사용")

    # undetected-chromedriver로 시도 (최대 재시도 횟수만큼)
    for retry in range(max_retries):
        try:
            logger.info(f"undetected-chromedriver 시도 {retry + 1}/{max_retries}...")

            # 프록시 없이 먼저 시도
            result = extract_product_info_with_undetected(product_url, None)
            if result and len(result) > 1000:  # HTML이 충분히 길면 성공
                logger.info("undetected-chromedriver 크롤링 성공! (프록시 없이)")
                return result

            # 프록시가 있으면 프록시로 시도
            if proxy:
                logger.info(f"undetected-chromedriver 시도 {retry + 1}/{max_retries} (프록시 사용)...")
                result = extract_product_info_with_undetected(product_url, proxy)
                if result and len(result) > 1000:
                    logger.info("undetected-chromedriver 크롤링 성공! (프록시 사용)")
                    return result

            logger.warning(f"undetected-chromedriver 시도 실패 ({retry + 1}/{max_retries})")
            time.sleep(2)  # 재시도 전 대기

        except Exception as e:
            logger.error(f"undetected-chromedriver 시도 중 오류: {str(e)}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
            time.sleep(2)  # 오류 발생 시 대기

    # 모든 시도가 실패하면 None 반환
    logger.warning("모든 크롤링 시도 실패")
    return None

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Coupang Proxy Service</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .endpoint { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }
            code { background: #e8e8e8; padding: 2px 4px; border-radius: 3px; }
            .status { color: #28a745; font-weight: bold; }
            a { color: #007bff; text-decoration: none; }
            a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <h1>🛒 Coupang Proxy Service</h1>
        <p class="status">✅ 서비스 정상 운영 중 (Python + undetected-chromedriver)</p>
        
        <h2>📡 API 엔드포인트</h2>
        
        <div class="endpoint">
            <h3>HTML 프록시</h3>
            <code>GET /proxy?url=쿠팡URL</code>
            <p>쿠팡 페이지를 HTML 형태로 반환</p>
        </div>
        
        <div class="endpoint">
            <h3>프록시 사용</h3>
            <code>GET /proxy?url=쿠팡URL&proxy=IP:PORT</code>
            <p>지정한 프록시를 통해 접근</p>
        </div>
        
        <h2>💡 사용 예시</h2>
        <p><a href="/proxy?url=https://www.coupang.com/vp/products/7959990775?vendorItemId=22491901734&itemId=90690647897" target="_blank">
        테스트: 쿠팡 상품 페이지 보기</a></p>
        
        <p><a href="/health">서버 상태 확인</a></p>
        
        <h3>⚙️ 지원 기능</h3>
        <ul>
            <li>✅ undetected-chromedriver 사용</li>
            <li>✅ 단축 URL 자동 해결</li>
            <li>✅ 모바일 버전 자동 변환</li>
            <li>✅ 프록시 지원</li>
            <li>✅ CORS 헤더 자동 추가</li>
            <li>✅ 자동 재시도 (최대 3회)</li>
        </ul>
    </body>
    </html>
    '''

@app.route('/proxy')
def proxy_coupang():
    """쿠팡 페이지를 프록시해서 HTML 반환"""
    url = request.args.get('url')
    proxy = request.args.get('proxy')
    
    if not url:
        return "Missing url parameter", 400
    
    logger.info(f"프록시 요청 받음: {url}")
    
    # HTML 가져오기 (원본 extract_product_info 함수 사용)
    html_content = extract_product_info(url, max_retries=3, proxy=proxy)
    
    if html_content:
        # CORS 헤더와 함께 HTML 반환
        response = Response(html_content, mimetype='text/html; charset=utf-8')
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        logger.info(f"HTML 반환 성공 ({len(html_content)} bytes)")
        return response
    else:
        logger.error("페이지 가져오기 실패")
        return "Failed to fetch page", 500

@app.route('/health')
def health():
    return jsonify({
        "status": "OK",
        "service": "Coupang Proxy",
        "timestamp": time.time(),
        "python_version": "3.9",
        "selenium_support": True,
        "undetected_chromedriver": True
    })

# OPTIONS 요청 처리 (CORS)
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = Response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
