#!/usr/bin/env python3

"""
하이브리드 NY Post 스크래퍼
HTTP 우선 → 실패시 Selenium 자동 사용
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict
from datetime import datetime
import logging
from urllib.parse import quote
import re
import time

logger = logging.getLogger(__name__)

class HybridNYPostScraper:
    def __init__(self):
        self.base_url = "https://nypost.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.selenium_available = self._check_selenium_availability()
    
    def _check_selenium_availability(self) -> bool:
        """Selenium 사용 가능 여부 확인"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            return True
        except ImportError:
            logger.warning("Selenium이 설치되어 있지 않습니다. HTTP 방식만 사용합니다.")
            return False
    
    def search_news(self, query: str, limit: int = 10) -> List[Dict]:
        """하이브리드 뉴스 검색: HTTP → Selenium"""
        logger.info(f"NY Post 하이브리드 검색: {query}")
        
        # 1단계: HTTP 시도 (실제 검색 시도)
        articles = self._search_with_http(query, limit)
        
        if articles and len(articles) >= 3:
            logger.info(f"HTTP로 {len(articles)}개 기사 찾음")
            return articles
        
        # 2단계: Selenium 시도
        if self.selenium_available:
            logger.info("HTTP 결과 부족, Selenium으로 시도")
            selenium_articles = self._search_with_selenium(query, limit)
            
            if selenium_articles:
                logger.info(f"Selenium으로 {len(selenium_articles)}개 기사 찾음")
                return selenium_articles
        
        # 3단계: 폴백 - 홈페이지 최신 뉴스
        logger.info("검색 실패, 홈페이지 최신 뉴스로 폴백")
        return self._get_homepage_articles(limit)
    
    def _search_with_http(self, query: str, limit: int) -> List[Dict]:
        """HTTP 기반 검색 (실제 검색 시도)"""
        try:
            # NY Post 검색 URL 패턴들 시도
            search_patterns = [
                f"https://nypost.com/search/{quote(query)}/",
                f"https://nypost.com/?s={quote(query)}",
                f"https://nypost.com/search/?q={quote(query)}"
            ]
            
            for search_url in search_patterns:
                try:
                    response = requests.get(search_url, headers=self.headers, timeout=10)
                    response.raise_for_status()
                    
                    if len(response.text) > 5000:
                        articles = self._extract_search_results(response.text, limit, query)
                        if articles:
                            logger.info(f"NY Post HTTP 검색 결과: {len(articles)}개 기사 찾음")
                            return articles
                except:
                    continue
            
            # 모든 검색 패턴 실패시
            logger.info("NY Post HTTP 검색 실패")
            return []
            
        except Exception as e:
            logger.debug(f"HTTP 검색 실패: {e}")
            return []
    
    def _extract_search_results(self, html_content: str, limit: int, query: str = '') -> List[Dict]:
        """HTML에서 검색 결과 추출 (기존 NY Post 스크래퍼 로직)"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # NY Post 검색 결과 패턴 찾기
            selectors = [
                '.search-result',
                '.article',
                '.story',
                'article',
                '.post',
                '[class*="search"]',
                '[class*="article"]',
                '[class*="story"]',
                '[class*="post"]',
                'a[href*="nypost.com"]',
                'h2 a',
                'h3 a'
            ]
            
            found_items = set()
            
            for selector in selectors:
                elements = soup.select(selector)
                
                for element in elements:
                    try:
                        title = ''
                        url = ''
                        summary = ''
                        image_url = ''
                        
                        # 요소 타입에 따른 처리
                        if element.name == 'a':
                            # 링크 요소인 경우
                            url = element.get('href', '')
                            title = element.get_text(strip=True)
                            
                            # 부모 요소에서 더 많은 정보 가져오기
                            parent = element.find_parent(['article', 'div'])
                            if parent:
                                # 더 나은 제목 찾기
                                title_elem = parent.find(['h1', 'h2', 'h3', 'h4'])
                                if title_elem and len(title_elem.get_text(strip=True)) > len(title):
                                    title = title_elem.get_text(strip=True)
                                
                                # 요약 찾기
                                summary_elem = parent.find(['p', '.excerpt', '.summary', '.description'])
                                if summary_elem:
                                    summary = summary_elem.get_text(strip=True)
                                
                                # 이미지 찾기 - 기존 로직 사용
                                image_url = self._extract_nypost_image(element, url)
                        
                        else:
                            # article, div 등의 컨테이너 요소인 경우
                            link_elem = element.find('a', href=True)
                            if link_elem:
                                url = link_elem.get('href', '')
                                
                                # 제목 찾기
                                title_elem = element.find(['h1', 'h2', 'h3', 'h4']) or link_elem
                                title = title_elem.get_text(strip=True) if title_elem else ''
                                
                                # 요약 찾기
                                summary_elem = element.find(['p', '.excerpt', '.summary', '.description'])
                                if summary_elem:
                                    summary = summary_elem.get_text(strip=True)
                                
                                # 이미지 찾기 - 기존 로직 사용
                                image_url = self._extract_nypost_image(link_elem, url)
                        
                        # 기본 검증
                        if not title or not url or len(title) < 10:
                            continue
                        
                        # URL 정규화
                        if url.startswith('/'):
                            url = self.base_url + url
                        elif not url.startswith('http'):
                            continue
                        
                        # NY Post URL인지 확인
                        if 'nypost.com' not in url:
                            continue
                        
                        # 이미지 URL 정규화
                        if image_url and not image_url.startswith('http'):
                            if image_url.startswith('//'):
                                image_url = 'https:' + image_url
                            elif image_url.startswith('/'):
                                image_url = self.base_url + image_url
                        
                        # 중복 체크
                        item_key = (title, url)
                        if item_key in found_items:
                            continue
                        found_items.add(item_key)
                        
                        # NY Post 날짜 추출
                        published_date = self._extract_nypost_date(element, url)
                        
                        article = {
                            'title': title,
                            'url': url,
                            'summary': summary[:300] if summary else '',
                            'published_date': published_date,
                            'source': 'NY Post',
                            'category': self._extract_category_from_url(url),
                            'scraped_at': datetime.now().isoformat(),
                            'relevance_score': 0.5,  # 검색 결과이므로 관련도 점수
                            'image_url': image_url
                        }
                        
                        articles.append(article)
                        
                        if len(articles) >= limit:
                            break
                            
                    except Exception as e:
                        logger.debug(f"NY Post 요소 파싱 실패: {e}")
                        continue
                
                if len(articles) >= limit:
                    break
                    
        except Exception as e:
            logger.error(f"NY Post HTML 파싱 실패: {e}")
        
        return articles[:limit]
    
    def _extract_nypost_image(self, link_elem, article_url: str) -> str:
        """NY Post 기사에서 고유한 이미지 추출 (기존 로직)"""
        image_url = ''
        
        try:
            # 1. 링크 요소 자체에서 이미지 찾기
            img_elem = link_elem.find('img')
            if img_elem:
                for attr in ['src', 'data-src', 'data-lazy-src', 'data-original', 'data-img']:
                    img_src = img_elem.get(attr, '')
                    if img_src and self._is_valid_nypost_image(img_src):
                        image_url = img_src
                        break
            
            # 2. 링크의 직접 부모에서 이미지 찾기
            if not image_url:
                parent = link_elem.find_parent()
                while parent and not image_url:
                    img_elem = parent.find('img')
                    if img_elem:
                        for attr in ['src', 'data-src', 'data-lazy-src', 'data-original']:
                            img_src = img_elem.get(attr, '')
                            if img_src and self._is_valid_nypost_image(img_src):
                                image_url = img_src
                                break
                    parent = parent.find_parent()
                    if parent and parent.name in ['body', 'html']:
                        break
            
            # 3. 형제 요소에서 이미지 찾기
            if not image_url:
                siblings = [link_elem.find_previous_sibling(), link_elem.find_next_sibling()]
                for sibling in siblings:
                    if sibling:
                        img_elem = sibling.find('img') if hasattr(sibling, 'find') else None
                        if img_elem:
                            for attr in ['src', 'data-src', 'data-lazy-src', 'data-original']:
                                img_src = img_elem.get(attr, '')
                                if img_src and self._is_valid_nypost_image(img_src):
                                    image_url = img_src
                                    break
                        if image_url:
                            break
                
        except Exception as e:
            logger.debug(f"NY Post 이미지 추출 실패: {e}")
        
        return image_url
    
    def _is_valid_nypost_image(self, url: str) -> bool:
        """NY Post 이미지가 유효하고 고유한지 확인"""
        if not url or len(url) < 10:
            return False
        
        # 제외할 이미지 패턴들
        exclude_patterns = [
            'logo',
            'avatar',
            'icon',
            'placeholder',
            'default',
            'blank',
            'spacer',
            'tracking',
            'pixel',
            'nypost-logo',
            'facebook',
            'twitter',
            'linkedin',
            'whatsapp',
            'telegram',
            'instagram',
            'pinterest'
        ]
        
        url_lower = url.lower()
        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False
        
        # 유효한 이미지 확장자 확인
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        if any(ext in url_lower for ext in valid_extensions):
            return True
        
        # NY Post CDN 패턴 확인
        if any(domain in url for domain in ['nypost.com', 'nypostcom.files.wordpress.com', 'thenypost.files.wordpress.com']):
            return True
        
        return False
    
    def _extract_nypost_date(self, element, url: str) -> str:
        """NY Post 날짜 추출 (기존 로직)"""
        try:
            # 1. 요소에서 날짜 텍스트 찾기
            date_selectors = [
                '.published-date',
                '.date',
                '.timestamp',
                'time',
                '[datetime]',
                '.meta-date',
                '.article-timestamp',
                '.entry-date'
            ]
            
            for selector in date_selectors:
                date_elem = element.find(selector)
                if date_elem:
                    date_text = date_elem.get('datetime') or date_elem.get_text(strip=True)
                    if date_text:
                        return self._format_date(date_text)
            
            # 2. URL에서 날짜 패턴 찾기
            date_patterns = [
                r'/(\d{4})/(\d{1,2})/(\d{1,2})/',  # /2024/07/15/
                r'-(\d{4})-(\d{1,2})-(\d{1,2})',   # -2024-07-15
                r'/(\d{4})-(\d{1,2})-(\d{1,2})-'   # NY Post URL 패턴
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, url)
                if match:
                    groups = match.groups()
                    if len(groups) >= 3:
                        year, month, day = groups[:3]
                        try:
                            date_obj = datetime(int(year), int(month), int(day))
                            return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                        except:
                            continue
                            
        except Exception as e:
            logger.debug(f"NY Post 날짜 추출 실패: {e}")
        
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    def _format_date(self, date_str: str) -> str:
        """날짜 문자열을 GMT 형식으로 변환"""
        try:
            # 다양한 날짜 형식 시도
            date_formats = [
                '%Y-%m-%d',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d %H:%M:%S',
                '%d %b %Y',
                '%b %d, %Y',
                '%d/%m/%Y',
                '%m/%d/%Y',
                '%B %d, %Y'  # NY Post 형식
            ]
            
            for fmt in date_formats:
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                except:
                    continue
                    
        except Exception as e:
            logger.debug(f"날짜 형식 변환 실패: {e}")
        
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    def _search_with_selenium(self, query: str, limit: int) -> List[Dict]:
        """Selenium 기반 검색"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.common.keys import Keys
            
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument(f'--user-agent={self.headers["User-Agent"]}')
            
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(10)
            
            articles = []
            
            try:
                # NY Post 메인 페이지로 이동
                driver.get(self.base_url)
                time.sleep(2)
                
                # 검색창 찾기 및 검색어 입력
                search_selectors = [
                    'input[name="s"]',
                    'input[type="search"]',
                    '.search-field',
                    '#search',
                    '[placeholder*="Search"]'
                ]
                
                search_input = None
                for selector in search_selectors:
                    try:
                        search_input = driver.find_element(By.CSS_SELECTOR, selector)
                        if search_input.is_displayed():
                            break
                    except:
                        continue
                
                if search_input:
                    search_input.clear()
                    search_input.send_keys(query)
                    search_input.send_keys(Keys.RETURN)
                    time.sleep(3)
                    
                    # 검색 결과 추출
                    articles = self._extract_selenium_results(driver, limit)
                
                return articles
                
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error(f"Selenium 검색 실패: {e}")
            return []
    
    def _extract_selenium_results(self, driver, limit: int) -> List[Dict]:
        """Selenium에서 검색 결과 추출"""
        articles = []
        
        try:
            # 검색 결과 찾기
            selectors = [
                'article',
                '[class*="story"]',
                '[class*="post"]',
                'a[href*="nypost.com"]',
                'h2 a',
                'h3 a'
            ]
            
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for element in elements[:limit*2]:
                        article = self._extract_article_from_element(element, driver)
                        if article and article not in articles:
                            articles.append(article)
                            
                            if len(articles) >= limit:
                                break
                    
                    if articles:
                        break
                        
                except Exception as e:
                    continue
            
            return articles
            
        except Exception as e:
            logger.debug(f"Selenium 결과 추출 실패: {e}")
            return []
    
    def _extract_article_from_element(self, element, driver) -> Dict:
        """Selenium 요소에서 기사 정보 추출"""
        try:
            # 제목 추출
            title = ""
            try:
                title = element.text.strip()
                if not title:
                    title = element.get_attribute('textContent').strip()
            except:
                pass
            
            # URL 추출
            url = ""
            try:
                if element.tag_name == 'a':
                    url = element.get_attribute('href')
                else:
                    link = element.find_element(By.TAG_NAME, 'a')
                    url = link.get_attribute('href')
            except:
                pass
            
            # 기본 검증
            if not title or not url or len(title) < 10:
                return None
            
            # URL 정규화
            if url.startswith('/'):
                url = self.base_url + url
            
            # NY Post 도메인 확인
            if 'nypost.com' not in url:
                return None
            
            return {
                'title': title[:200],
                'url': url,
                'summary': '',
                'published_date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),
                'source': 'NY Post',
                'category': self._extract_category_from_url(url),
                'scraped_at': datetime.now().isoformat(),
                'relevance_score': 0.5,
                'image_url': ''  # Selenium에서는 이미지 추출 생략
            }
            
        except Exception as e:
            return None
    
    def _get_homepage_articles(self, limit: int) -> List[Dict]:
        """홈페이지에서 최신 뉴스 가져오기 (폴백)"""
        try:
            response = requests.get(self.base_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = []
            
            # NY Post 홈페이지에서 기사 링크 찾기
            selectors = [
                'h2 a[href*="nypost.com"]',
                'h3 a[href*="nypost.com"]',
                'article a[href*="nypost.com"]',
                '.story-headline a',
                '.entry-title a',
                'a[href*="/2024/"]',  # NY Post URL 패턴
                'a[href*="/2025/"]'
            ]
            
            found_urls = set()
            
            for selector in selectors:
                links = soup.select(selector)
                
                for link in links:
                    href = link.get('href', '')
                    title = link.get_text(strip=True)
                    
                    if not href or not title or len(title) < 10:
                        continue
                    
                    if href.startswith('/'):
                        href = self.base_url + href
                    
                    if 'nypost.com' not in href or href in found_urls:
                        continue
                    found_urls.add(href)
                    
                    # 이미지 추출
                    image_url = self._extract_nypost_image(link, href)
                    if image_url:
                        if image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        elif image_url.startswith('/'):
                            image_url = self.base_url + image_url
                    
                    # NY Post 날짜 추출
                    published_date = self._extract_nypost_date(link, href)
                    
                    article = {
                        'title': title,
                        'url': href,
                        'summary': '',
                        'published_date': published_date,
                        'source': 'NY Post',
                        'category': self._extract_category_from_url(href),
                        'scraped_at': datetime.now().isoformat(),
                        'relevance_score': 1,
                        'image_url': image_url
                    }
                    
                    articles.append(article)
                    if len(articles) >= limit:
                        break
                
                if len(articles) >= limit:
                    break
            
            return articles
            
        except Exception as e:
            logger.error(f"홈페이지 폴백 실패: {e}")
            return []
    
    def _extract_category_from_url(self, url: str) -> str:
        """URL에서 카테고리 추출"""
        try:
            if '/news/' in url:
                return 'news'
            elif '/business/' in url or '/economy/' in url:
                return 'business'
            elif '/sports/' in url:
                return 'sports'
            elif '/tech/' in url or '/technology/' in url:
                return 'technology'
            elif '/entertainment/' in url or '/celebrity/' in url:
                return 'entertainment'
            elif '/metro/' in url or '/city/' in url:
                return 'news'
            else:
                return 'news'
        except:
            return 'news'
    
    def get_latest_news(self, category: str = 'news', limit: int = 10) -> List[Dict]:
        """카테고리별 최신 뉴스 가져오기"""
        return self._get_homepage_articles(limit) 