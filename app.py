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

def extract_product_info_with_undetected(product_url, proxy=None):
    """원본 Python 코드와 완전 동일한 상품 정보 추출 함수"""
    driver = None
    try:
        logger.info(f"undetected-chromedriver를 사용하여 상품 정보 추출 시도: {product_url}")

        # undetected_chromedriver 설정 (원본과 동일)
        try:
            temp_dir = os.path.join(os.path.expanduser('~'), '.temp_chromedriver')
            os.makedirs(temp_dir, exist_ok=True)
            os.environ['UC_DRIVER_CACHE_DIR'] = temp_dir

            if not hasattr(uc, 'TARGET_VERSION'):
                uc.TARGET_VERSION = 114

            try:
                import socket
                socket.setdefaulttimeout(30)
            except:
                pass

        except Exception as e:
            logger.error(f"undetected_chromedriver 설정 오류: {str(e)}")

     # Chrome 옵션 설정 (가상 디스플레이 환경용)
        options = uc.ChromeOptions()
        
        # 기본 보안 및 안정성 설정
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        
        # 자동화 감지 방지 (핵심)
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--exclude-switches=enable-automation")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # 브라우저 동작 설정
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-extensions-file-access-check")
        options.add_argument("--disable-plugins-discovery")
        
        # 네트워크 및 보안 설정
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")
        options.add_argument("--disable-web-security")
        options.add_argument("--dns-prefetch-disable")
        
        # 성능 최적화
        options.add_argument("--blink-settings=imagesEnabled=false")
        
        # 언어 및 지역 설정
        options.add_argument("--lang=ko-KR,ko")
        
        # 가상 디스플레이 설정
        options.add_argument("--display=:99")
        options.add_argument("--start-maximized")
        
        # User-Agent 설정
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # 헤드리스 모드 제거됨 - 가상 디스플레이 사용

        # 프록시 설정
        if proxy:
            options.add_argument(f'--proxy-server={proxy}')
            logger.info(f"프록시 설정: {proxy}")

        # 브라우저 시작
        try:
            driver = uc.Chrome(options=options, use_subprocess=True)
            driver.set_page_load_timeout(30)
        except Exception as e:
            logger.error(f"Chrome 드라이버 초기화 오류: {str(e)}")
            return None

        try:
            # 쿠팡 홈페이지 먼저 방문
            logger.info("쿠팡 홈페이지 사전 방문...")
            driver.get("https://m.coupang.com")
            time.sleep(3)

            # 상품 페이지 방문
            logger.info(f"상품 페이지 방문: {product_url}")
            driver.get(product_url)
            time.sleep(5)

            # 페이지 로드 대기
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except TimeoutException:
                logger.warning("페이지 로드 타임아웃")
                return None

            # 상품 정보 추출 (원본 로직과 동일)
            result = {}

            # 제품 ID 추출
            product_id_match = re.search(r'/products/(\d+)', product_url)
            if product_id_match:
                result["productId"] = product_id_match.group(1)

            # 제품명 추출
            try:
                title = driver.title
                if "사이트에 연결할 수 없음" in title or "Access Denied" in title:
                    logger.error("사이트 접근이 차단되었습니다.")
                    return None

                result["productName"] = title.split(" - ")[0] if " - " in title else title

                # 제품명 추출 백업 방법 (h1 태그에서)
                if not result.get("productName") or len(result["productName"]) < 5:
                    h1_elements = driver.find_elements(By.TAG_NAME, "h1")
                    if h1_elements:
                        result["productName"] = h1_elements[0].text.strip()
                        logger.info(f"H1 태그에서 제품명 추출: {result['productName']}")
            except Exception as e:
                logger.warning(f"제품명 추출 중 오류: {str(e)}")

            # 가격 추출 (원본과 동일한 복잡한 로직)
            try:
                # 1. 정확한 가격 클래스로 시도 (현재가)
                final_price_elements = driver.find_elements(By.CSS_SELECTOR, ".price-amount.final-price-amount")
                if final_price_elements:
                    price_text = final_price_elements[0].text.strip()
                    price_match = re.search(r'([0-9,]+)(?:원)?', price_text)
                    if price_match:
                        result["price"] = price_match.group(1).replace(",", "") + "원"
                        logger.info(f"현재가 추출 성공: {result['price']}")

                # 2. 정확한 가격 클래스로 시도 (원가)
                original_price_elements = driver.find_elements(By.CSS_SELECTOR, ".price-amount.original-price-amount")
                if original_price_elements:
                    orig_text = original_price_elements[0].text.strip()
                    orig_match = re.search(r'([0-9,]+)(?:원)?', orig_text)
                    if orig_match:
                        result["originPrice"] = orig_match.group(1).replace(",", "") + "원"
                        logger.info(f"원가 추출 성공: {result['originPrice']}")

                # 3. 백업 선택자들
                if "price" not in result:
                    backup_price_selectors = [
                        ".PriceInfo_finalPrice__qniie",
                        ".total-price strong",
                        ".total-price",
                        ".sale-price",
                        ".product-price",
                        ".price-value"
                    ]

                    for selector in backup_price_selectors:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            price_text = elements[0].text.strip()
                            price_match = re.search(r'([0-9,]+)(?:원)?', price_text)
                            if price_match:
                                result["price"] = price_match.group(1).replace(",", "") + "원"
                                logger.info(f"백업 선택자로 가격 추출: {result['price']}")
                                break

                # 4. 페이지 소스에서 가격 패턴 찾기
                if "price" not in result:
                    page_source = driver.page_source
                    price_matches = re.findall(r'([0-9,]{3,})원', page_source)
                    if price_matches:
                        prices = []
                        for match in price_matches:
                            try:
                                price_value = int(match.replace(",", ""))
                                if price_value > 100:
                                    prices.append(price_value)
                            except:
                                continue

                        if prices:
                            prices.sort()
                            result["price"] = str(prices[0]) + "원"
                            if "originPrice" not in result:
                                result["originPrice"] = str(prices[-1] if len(prices) > 1 else prices[0]) + "원"
                            logger.info(f"일반 패턴 검색으로 가격 추출: 현재가 {result['price']}, 원가 {result['originPrice']}")

            except Exception as e:
                logger.warning(f"가격 추출 중 오류: {str(e)}")

            # 가격 정보 보완
            if "price" in result and "originPrice" not in result:
                result["originPrice"] = result["price"]
            elif "originPrice" in result and "price" not in result:
                result["price"] = result["originPrice"]

            # 배송 정보
            try:
                page_source = driver.page_source
                result["isRocket"] = "Y" if "로켓배송" in page_source else "N"
                result["freeShipping"] = "Y" if "무료배송" in page_source else "N"
            except Exception as e:
                logger.warning(f"배송 정보 추출 중 오류: {str(e)}")
                result["isRocket"] = "N"
                result["freeShipping"] = "N"

            # HTML도 함께 반환
            result["html"] = driver.page_source
            result["html_length"] = len(driver.page_source)

            # 상품 정보 확인
            if "productName" not in result or not result["productName"]:
                logger.warning("제품명 추출 실패")
                return None

            logger.info(f"상품 정보 추출 완료: {result.get('productName')}")
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
        logger.error(f"undetected-chromedriver 사용 중 오류 발생: {str(e)}")
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
