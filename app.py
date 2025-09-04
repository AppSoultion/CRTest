from flask import Flask, request, jsonify, Response
import requests
import re
import time
import random
import logging
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc

app = Flask(__name__)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
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
        return None
    except Exception as e:
        logger.error(f"단축 URL 해결 중 오류: {str(e)}")
        return None

def process_product_url(url):
    """쿠팡 상품 URL 처리"""
    if "coupang.com" not in url:
        return None
    
    # 모바일 버전으로 변환
    if "www.coupang.com" in url:
        url = url.replace("www.coupang.com", "m.coupang.com")
    if "/vp/products/" in url:
        url = url.replace("/vp/products/", "/vm/products/")
    
    logger.info(f"처리된 URL: {url}")
    return url

def get_coupang_html(product_url, proxy=None):
    """쿠팡 페이지 HTML 가져오기"""
    driver = None
    try:
        logger.info(f"크롤링 시작: {product_url}")
        
        # Chrome 옵션 설정
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--lang=ko-KR,ko")
        options.add_argument("--blink-settings=imagesEnabled=false")
        
        # 헤드리스 모드 (서버 환경)
        if os.environ.get('PRODUCTION'):
            options.add_argument("--headless")
        
        # 프록시 설정
        if proxy:
            options.add_argument(f'--proxy-server={proxy}')
            logger.info(f"프록시 설정: {proxy}")
        
        driver = uc.Chrome(options=options, use_subprocess=True)
        driver.set_page_load_timeout(30)
        
        # 쿠팡 홈페이지 먼저 방문
        logger.info("쿠팡 홈페이지 사전 방문...")
        driver.get("https://m.coupang.com")
        time.sleep(3)
        
        # 상품 페이지 방문
        logger.info(f"상품 페이지 방문: {product_url}")
        driver.get(product_url)
        time.sleep(5)
        
        # 페이지 로드 대기
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # HTML 반환
        html_content = driver.page_source
        logger.info("HTML 추출 완료")
        
        return html_content
        
    except Exception as e:
        logger.error(f"크롤링 중 오류: {str(e)}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("브라우저 정상 종료")
            except:
                pass

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Coupang Proxy Service</title>
        <meta charset="utf-8">
    </head>
    <body>
        <h1>Coupang Proxy Service</h1>
        <h2>사용법:</h2>
        <p><code>GET /proxy?url=쿠팡URL</code></p>
        <p><code>GET /api/crawl?url=쿠팡URL</code> (JSON 응답)</p>
        
        <h3>예시:</h3>
        <p><a href="/proxy?url=https://www.coupang.com/vp/products/7959990775?vendorItemId=22491901734&itemId=90690647897">
        쿠팡 상품 페이지 보기</a></p>
        
        <p>상태: 정상 운영 중</p>
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
    
    # 단축 URL 처리
    if "link.coupang.com" in url:
        resolved_url = resolve_short_url(url)
        if resolved_url:
            url = resolved_url
        else:
            return "Failed to resolve short URL", 400
    
    # URL 처리
    processed_url = process_product_url(url)
    if not processed_url:
        return "Invalid Coupang URL", 400
    
    # HTML 가져오기
    html_content = get_coupang_html(processed_url, proxy)
    
    if html_content:
        # HTML 응답 반환
        response = Response(html_content, mimetype='text/html')
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    else:
        return "Failed to fetch page", 500

@app.route('/api/crawl')
def api_crawl():
    """API 형태로 크롤링 결과 반환"""
    url = request.args.get('url')
    proxy = request.args.get('proxy')
    
    if not url:
        return jsonify({"error": "Missing url parameter"}), 400
    
    # URL 처리 과정은 동일
    if "link.coupang.com" in url:
        resolved_url = resolve_short_url(url)
        if resolved_url:
            url = resolved_url
        else:
            return jsonify({"error": "Failed to resolve short URL"}), 400
    
    processed_url = process_product_url(url)
    if not processed_url:
        return jsonify({"error": "Invalid Coupang URL"}), 400
    
    html_content = get_coupang_html(processed_url, proxy)
    
    if html_content:
        return jsonify({
            "success": True,
            "url": processed_url,
            "html": html_content,
            "length": len(html_content)
        })
    else:
        return jsonify({"error": "Failed to fetch page"}), 500

@app.route('/health')
def health():
    return jsonify({
        "status": "OK",
        "service": "Coupang Proxy",
        "timestamp": time.time()
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
