# app.py - 원본 Python 로직과 동일하게 데이터 추출 중심
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
        session = requests.Session()
        response = session.head(short_url, allow_redirects=False)
        if 300 <= response.status_code < 400:
            redirect_url = response.headers.get('Location')
            if redirect_url:
                logger.info(f"단축 URL 리다이렉트 발견: {redirect_url}")
                if "coupang.com" in redirect_url:
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

def find_chrome_executable():
    """Chrome 실행 파일 경로 찾기"""
    possible_paths = [
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",  
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/opt/google/chrome/chrome",
        "/snap/bin/chromium"
    ]
    
    for path in possible_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            logger.info(f"Chrome 실행 파일 발견: {path}")
            return path
    
    # 시스템 PATH에서 찾기
    import subprocess
    try:
        result = subprocess.run(['which', 'google-chrome-stable'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            path = result.stdout.strip()
            logger.info(f"PATH에서 Chrome 발견: {path}")
            return path
    except:
        pass
    
    logger.error("Chrome 실행 파일을 찾을 수 없습니다")
    return None

def get_chrome_path():
    chrome_path = "/usr/bin/google-chrome-stable"
    if os.path.exists(chrome_path):
        return chrome_path
    else:
        logger.error("Chrome not found")
        return None


def extract_product_info_with_undetected(product_url, proxy=None):
    """undetected-chromedriver를 사용하여 상품 정보 추출 (Chrome 경로 지정)"""
    driver = None
    try:
        logger.info(f"undetected-chromedriver를 사용하여 상품 정보 추출 시도: {product_url}")

        # Chrome 옵션 설정 (최소한으로 유지)
        options = uc.ChromeOptions()
        
        # 필수 보안 설정
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-setuid-sandbox")
        
        # 자동화 감지 방지
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        # 기본 설정
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        options.add_argument("--lang=ko-KR,ko")
        
        # 가상 디스플레이 사용 (헤드리스 모드 없이)
        options.add_argument("--display=:99")
        options.add_argument("--window-size=1280,1024")
        
        # User-Agent 설정
        options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
        
        # 프록시 설정
        if proxy:
            options.add_argument(f'--proxy-server={proxy}')
            logger.info(f"프록시 설정: {proxy}")

        # Chrome 브라우저 시작 (경로 명시적 지정)
        try:
            # Chrome 실행 파일 경로를 명시적으로 지정
            chrome_path = get_chrome_path()
            if not chrome_path:
                return None
            
            driver = uc.Chrome(
                options=options,
                browser_executable_path=chrome_path,
                use_subprocess=True
            )
            
            # Chrome 바이너리가 존재하는지 확인
            if not os.path.exists(chrome_binary_path):
                logger.error(f"Chrome 실행 파일을 찾을 수 없습니다: {chrome_binary_path}")
                # 다른 가능한 경로들 확인
                possible_paths = [
                    "/usr/bin/google-chrome",
                    "/usr/bin/chromium-browser",
                    "/usr/bin/chromium",
                    "/opt/google/chrome/chrome"
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        chrome_binary_path = path
                        logger.info(f"Chrome 실행 파일 발견: {chrome_binary_path}")
                        break
                else:
                    logger.error("Chrome 실행 파일을 찾을 수 없습니다")
                    return None
            
            # Chrome 버전 확인
            try:
                import subprocess
                result = subprocess.run([chrome_binary_path, '--version'], 
                                      capture_output=True, text=True, timeout=10)
                logger.info(f"Chrome 버전: {result.stdout.strip()}")
            except Exception as e:
                logger.warning(f"Chrome 버전 확인 실패: {str(e)}")
            
            # undetected_chromedriver에 Chrome 경로 지정
            driver = uc.Chrome(
                options=options, 
                use_subprocess=True,
                browser_executable_path=chrome_binary_path,
                driver_executable_path=None  # 자동으로 다운로드하도록
            )
            
            driver.set_page_load_timeout(30)
            logger.info("Chrome 브라우저 초기화 성공")
            
        except Exception as e:
            logger.error(f"Chrome 드라이버 초기화 오류: {str(e)}")
            
            # 대안: 시스템 환경변수 설정 후 재시도
            try:
                import subprocess
                
                # Chrome과 ChromeDriver가 PATH에 있는지 확인
                chrome_check = subprocess.run(['which', 'google-chrome-stable'], 
                                            capture_output=True, text=True)
                if chrome_check.returncode == 0:
                    logger.info(f"Chrome 경로: {chrome_check.stdout.strip()}")
                
                # 다시 시도 (경로 지정 없이)
                driver = uc.Chrome(options=options, use_subprocess=True)
                driver.set_page_load_timeout(30)
                logger.info("Chrome 브라우저 초기화 성공 (두 번째 시도)")
                
            except Exception as e2:
                logger.error(f"Chrome 드라이버 재시도 실패: {str(e2)}")
                return None

        try:
            # 쿠팡 홈페이지 먼저 방문
            logger.info("쿠팡 홈페이지 사전 방문...")
            driver.get("https://m.coupang.com")
            time.sleep(5)  # 더 긴 대기 시간

            # 상품 페이지 방문
            logger.info(f"상품 페이지 방문: {product_url}")
            driver.get(product_url)
            time.sleep(8)  # 충분한 로딩 시간

            # 페이지 로드 완료 대기
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                logger.info("페이지 로드 완료")
            except TimeoutException:
                logger.warning("페이지 로드 타임아웃, 계속 진행")

            # 페이지 제목 확인
            title = driver.title
            logger.info(f"페이지 제목: {title}")
            
            if "사이트에 연결할 수 없음" in title or "Access Denied" in title or "ERR_" in title:
                logger.error("사이트 접근이 차단되었거나 에러 페이지입니다.")
                
                # 페이지 소스 일부 로깅
                page_source_preview = driver.page_source[:500]
                logger.info(f"페이지 소스 미리보기: {page_source_preview}")
                
                return None

            # HTML 추출
            html_content = driver.page_source
            logger.info(f"HTML 추출 완료 ({len(html_content)} bytes)")
            
            # 실제 쿠팡 콘텐츠인지 확인
            if len(html_content) < 10000 or "coupang" not in html_content.lower():
                logger.warning("쿠팡 페이지가 아니거나 내용이 부족합니다")
                logger.info(f"페이지 소스 샘플: {html_content[:1000]}")
                return None

            # 간단한 상품 정보 추출도 시도
            result = {
                "html": html_content,
                "html_length": len(html_content),
                "title": title
            }
            
            # 제품 ID 추출
            product_id_match = re.search(r'/products/(\d+)', product_url)
            if product_id_match:
                result["productId"] = product_id_match.group(1)
            
            return result

        finally:
            # 브라우저 종료
            if driver:
                try:
                    driver.quit()
                    logger.info("크롬 브라우저가 정상적으로 종료되었습니다.")
                except Exception as e:
                    logger.warning(f"브라우저 종료 중 오류: {str(e)}")

    except Exception as e:
        logger.error(f"전체 프로세스 중 오류 발생: {str(e)}")
        import traceback
        logger.error(f"상세 오류: {traceback.format_exc()}")
        
        if driver:
            try:
                driver.quit()
            except:
                pass
        
        return None

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Coupang Data Extraction Service</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .endpoint { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }
            code { background: #e8e8e8; padding: 2px 4px; border-radius: 3px; }
            .status { color: #28a745; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>Coupang Data Extraction Service</h1>
        <p class="status">원본 Python 로직 기반 데이터 추출 서비스</p>
        
        <h2>API 엔드포인트</h2>
        
        <div class="endpoint">
            <h3>상품 정보 추출 (JSON)</h3>
            <code>GET /extract?url=쿠팡URL</code>
            <p>상품 정보를 JSON 형태로 반환</p>
        </div>
        
        <div class="endpoint">
            <h3>HTML만 가져오기</h3>
            <code>GET /html?url=쿠팡URL</code>
            <p>크롤링한 HTML을 텍스트로 반환</p>
        </div>
        
        <div class="endpoint">
            <h3>프록시 사용</h3>
            <code>GET /extract?url=쿠팡URL&proxy=IP:PORT</code>
        </div>
        
        <h2>사용 예시</h2>
        <p><a href="/extract?url=https://www.coupang.com/vp/products/7959990775?vendorItemId=22491901734&itemId=90690647897">
        테스트: 상품 정보 추출</a></p>
        
        <p><a href="/html?url=https://www.coupang.com/vp/products/7959990775?vendorItemId=22491901734&itemId=90690647897">
        테스트: HTML 가져오기</a></p>
    </body>
    </html>
    '''

@app.route('/extract')
def extract_product():
    """상품 정보를 JSON으로 추출 (원본 로직)"""
    url = request.args.get('url')
    proxy = request.args.get('proxy')
    
    if not url:
        return jsonify({"error": "Missing url parameter"}), 400
    
    logger.info(f"상품 정보 추출 요청: {url}")
    
    # URL 처리
    if "link.coupang.com" in url:
        resolved_url = resolve_short_url(url)
        if resolved_url:
            url = resolved_url
        else:
            return jsonify({"error": "Failed to resolve short URL"}), 400
    
    processed_url = process_product_url(url)
    if not processed_url:
        return jsonify({"error": "Invalid Coupang URL"}), 400
    
    # 상품 정보 추출
    result = extract_product_info_with_undetected(processed_url, proxy)
    
    if result:
        return jsonify({
            "success": True,
            "data": {
                "productId": result.get("productId"),
                "productName": result.get("productName"),
                "price": result.get("price"),
                "originPrice": result.get("originPrice"),
                "isRocket": result.get("isRocket"),
                "freeShipping": result.get("freeShipping")
            },
            "html_length": result.get("html_length", 0),
            "timestamp": time.time()
        })
    else:
        return jsonify({
            "success": False,
            "error": "Failed to extract product info"
        }), 500

@app.route('/html')
def get_html():
    """HTML을 텍스트 형태로 반환"""
    url = request.args.get('url')
    proxy = request.args.get('proxy')
    
    if not url:
        return "Missing url parameter", 400
    
    logger.info(f"HTML 가져오기 요청: {url}")
    
    # URL 처리
    if "link.coupang.com" in url:
        resolved_url = resolve_short_url(url)
        if resolved_url:
            url = resolved_url
        else:
            return "Failed to resolve short URL", 400
    
    processed_url = process_product_url(url)
    if not processed_url:
        return "Invalid Coupang URL", 400
    
    # HTML 가져오기
    result = extract_product_info_with_undetected(processed_url, proxy)
    
    if result and "html" in result:
        return result["html"], 200, {'Content-Type': 'text/plain; charset=utf-8'}
    else:
        return "Failed to fetch HTML", 500

@app.route('/health')
def health():
    return jsonify({
        "status": "OK",
        "service": "Coupang Data Extraction",
        "timestamp": time.time()
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
