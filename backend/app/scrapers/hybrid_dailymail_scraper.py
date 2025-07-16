#!/usr/bin/env python3

"""
하이브리드 Daily Mail 스크래퍼
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

class HybridDailyMailScraper:
    def __init__(self):
        self.base_url = "https://www.dailymail.co.uk"
        # 실제 작동하는 브라우저 헤더 (사용자 제공)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
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
        logger.info(f"Daily Mail 하이브리드 검색: {query}")
        
        # 1단계: HTTP 시도 (기존 로직 사용)
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
        """HTTP 기반 검색 (실제 검색 API 사용)"""
        try:
            # 실제 작동하는 Daily Mail 검색 URL
            search_url = f"https://www.dailymail.co.uk/home/search.html?offset=0&size=50&sel=site&searchPhrase={quote(query)}&sort=recent&type=article&type=video&type=permabox&days=all"
            
            logger.info(f"Daily Mail 검색 시도: {search_url}")
            
            # Referer 헤더 추가 (검색 페이지에서 온 것처럼)
            headers_with_referer = self.headers.copy()
            headers_with_referer['Referer'] = search_url
            
            response = requests.get(search_url, headers=headers_with_referer, timeout=15)
            response.raise_for_status()
            
            logger.info(f"Daily Mail 응답 성공: {response.status_code}, 길이: {len(response.text)}")
            
            articles = self._extract_search_results(response.text, limit, query)
            if articles:
                logger.info(f"Daily Mail HTTP 검색 결과: {len(articles)}개 기사 찾음")
                return articles
            else:
                logger.info("Daily Mail HTTP 검색 결과 없음")
                return []
            
        except requests.exceptions.Timeout:
            logger.warning("Daily Mail 검색 타임아웃 (15초)")
            return []
        except Exception as e:
            logger.error(f"Daily Mail HTTP 검색 실패: {e}")
            return []
    
    def _extract_search_results(self, html_content: str, limit: int, query: str = '') -> List[Dict]:
        """HTML에서 검색 결과 추출 (테스트에서 성공한 간단한 방법 사용)"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 테스트에서 55개 기사를 성공적으로 찾은 패턴들
            patterns = [
                'a[href*="/article/"]',
                'a[href*="/news/"]', 
                'a[href*="/sport/"]',
                'h2 a', 'h3 a',
                '.article-text a'
            ]
            
            found_links = set()
            
            # 모든 패턴으로 링크 수집
            for pattern in patterns:
                links = soup.select(pattern)
                
                for link in links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    # 기본 필터링
                    if not text or len(text) < 10 or not href:
                        continue
                    
                    # URL 정규화
                    if href.startswith('/'):
                        href = 'https://www.dailymail.co.uk' + href
                    elif not href.startswith('http'):
                        continue
                    
                    # Daily Mail URL 확인
                    if 'dailymail.co.uk' not in href:
                        continue
                    
                    # 중복 제거
                    if href in found_links:
                        continue
                    found_links.add(href)
                    
                    # 개선된 이미지 추출 로직 사용
                    image_url = self._extract_dailymail_image_improved(link, href)
                    
                    # 이미지 URL 정규화
                    if image_url:
                        if image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        elif image_url.startswith('/'):
                            image_url = 'https://www.dailymail.co.uk' + image_url
                        elif not image_url.startswith('http'):
                            image_url = 'https://www.dailymail.co.uk/' + image_url
                    
                    # 요약 찾기
                    summary = ''
                    parent = link.find_parent(['article', 'div', 'li'])
                    if parent:
                        summary_elem = parent.find(['p', '.excerpt', '.summary'])
                        if summary_elem:
                            summary = summary_elem.get_text(strip=True)[:300]
                    
                    article = {
                        'title': text,
                        'url': href,
                        'summary': summary,
                        'published_date': datetime.now().strftime('%Y-%m-%d'),
                        'source': 'Daily Mail',
                        'category': self._extract_category_from_url(href),
                        'scraped_at': datetime.now().isoformat(),
                        'relevance_score': 0.7,
                        'image_url': image_url
                    }
                    
                    articles.append(article)
                    
                    if len(articles) >= limit:
                        break
                
                if len(articles) >= limit:
                    break
            
            logger.info(f"Daily Mail 추출 완료: {len(articles)}개 기사")
            return articles[:limit]
                    
        except Exception as e:
            logger.error(f"Daily Mail HTML 파싱 실패: {e}")
            return []
    
    def _extract_sport_section_articles(self, html_content: str, limit: int) -> List[Dict]:
        """Daily Mail 스포츠 섹션에서 기사 추출"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Daily Mail 스포츠 기사 링크 찾기
            article_links = soup.find_all('a', href=True)
            sport_links = [link for link in article_links 
                          if '/sport/' in link.get('href', '') and 
                             '/article-' in link.get('href', '')]
            
            found_urls = set()
            
            for link in sport_links[:limit*2]:  # 여유분 확보
                try:
                    href = link.get('href')
                    title = link.get_text(strip=True)
                    
                    # URL 정규화
                    if href.startswith('/'):
                        href = self.base_url + href
                    elif not href.startswith('http'):
                        continue
                    
                    # 중복 제거 및 기본 검증
                    if not title or len(title) < 15 or href in found_urls:
                        continue
                    found_urls.add(href)
                    
                    # Daily Mail 이미지 추출
                    image_url = self._extract_dailymail_image(link, href)
                    
                    # Daily Mail 날짜 추출  
                    published_date = self._extract_dailymail_date(link, href)
                    
                    article = {
                        'title': title,
                        'url': href,
                        'summary': '',  # 스포츠 섹션에서는 요약 생략
                        'published_date': published_date,
                        'source': 'Daily Mail',
                        'category': 'Sports',
                        'scraped_at': datetime.now().isoformat(),
                        'relevance_score': 1,  # 스포츠 섹션이므로 높은 관련성
                        'image_url': image_url
                    }
                    
                    articles.append(article)
                    
                    if len(articles) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug(f"Daily Mail 스포츠 링크 파싱 실패: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Daily Mail 스포츠 섹션 HTML 파싱 실패: {e}")
        
        return articles[:limit]
    
    def _extract_dailymail_image_improved(self, link_elem, article_url: str) -> str:
        """개선된 Daily Mail 이미지 추출 - 메타 태그 우선"""
        try:
            # 1. 기사 페이지에서 메타 태그 이미지 추출
            response = requests.get(article_url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # OpenGraph 이미지
                og_image = soup.find('meta', property='og:image')
                if og_image and og_image.get('content'):
                    return og_image['content']
                
                # Twitter 이미지
                twitter_image = soup.find('meta', name='twitter:image')
                if twitter_image and twitter_image.get('content'):
                    return twitter_image['content']
                
                # Daily Mail 특별 메타 태그
                dm_image = soup.find('meta', property='article:image')
                if dm_image and dm_image.get('content'):
                    return dm_image['content']
                
                # 기사 본문의 첫 번째 이미지
                article_imgs = soup.find_all('img')
                for img in article_imgs:
                    src = img.get('src') or img.get('data-src')
                    if src and self._is_valid_dailymail_image(src):
                        if src.startswith('//'):
                            return 'https:' + src
                        elif src.startswith('/'):
                            return self.base_url + src
                        return src
                        
        except Exception as e:
            logger.debug(f"Daily Mail 메타 이미지 추출 실패: {e}")
        
        # 2. 폴백: 기존 방법 사용
        return self._extract_dailymail_image(link_elem, article_url)
    
    def _extract_dailymail_image(self, link_elem, article_url: str) -> str:
        """Daily Mail 기사에서 고유한 이미지 추출 (기존 로직)"""
        image_url = ''
        
        try:
            # 1. 링크 요소 자체에서 이미지 찾기
            img_elem = link_elem.find('img')
            if img_elem:
                for attr in ['src', 'data-src', 'data-lazy-src', 'data-original', 'data-img']:
                    img_src = img_elem.get(attr, '')
                    if img_src and self._is_valid_dailymail_image(img_src):
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
                            if img_src and self._is_valid_dailymail_image(img_src):
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
                                if img_src and self._is_valid_dailymail_image(img_src):
                                    image_url = img_src
                                    break
                        if image_url:
                            break
                
        except Exception as e:
            logger.debug(f"Daily Mail 이미지 추출 실패: {e}")
        
        return image_url
    
    def _is_valid_dailymail_image(self, url: str) -> bool:
        """Daily Mail 이미지가 유효하고 고유한지 확인"""
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
            'dailymail-logo',
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
        
        # Daily Mail CDN 패턴 확인
        if any(domain in url for domain in ['dailymail.co.uk', 'dmcdn.net', 'i.dailymail.co.uk']):
            return True
        
        return False
    
    def _extract_dailymail_date(self, element, url: str) -> str:
        """Daily Mail 날짜 추출 (기존 로직)"""
        try:
            # 1. 요소에서 날짜 텍스트 찾기
            date_selectors = [
                '.published-date',
                '.date',
                '.timestamp',
                'time',
                '[datetime]',
                '.meta-date',
                '.article-timestamp'
            ]
            
            for selector in date_selectors:
                date_elem = element.find(selector)
                if date_elem:
                    date_text = date_elem.get('datetime') or date_elem.get_text(strip=True)
                    if date_text:
                        return self._format_date(date_text)
            
            # 2. URL에서 날짜 패턴 찾기 (Daily Mail 특별 패턴)
            date_patterns = [
                r'/article-\d+/.*?(\d{4})-(\d{1,2})-(\d{1,2})',  # Daily Mail 기사 패턴
                r'/(\d{4})/(\d{1,2})/(\d{1,2})/',  # /2024/07/15/
                r'-(\d{4})-(\d{1,2})-(\d{1,2})',   # -2024-07-15
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
            logger.debug(f"Daily Mail 날짜 추출 실패: {e}")
        
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
                'Published: %H:%M, %d %B %Y'  # Daily Mail 특별 형식
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
                search_url = f"https://www.dailymail.co.uk/search?q={quote(query)}"
                driver.get(search_url)
                
                # 페이지 로딩 대기
                time.sleep(3)
                
                # 검색 결과 찾기
                selectors = [
                    'article',
                    '[class*="sch-res"]',
                    '[class*="article"]',
                    '[class*="story"]',
                    'a[href*="/article-"]',
                    'a[href*="/news/"]',
                    'a[href*="/sport/"]'
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
                
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error(f"Selenium 검색 실패: {e}")
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
            
            # Daily Mail 도메인 확인
            if 'dailymail.co.uk' not in url:
                return None
            
            return {
                'title': title[:200],
                'url': url,
                'summary': '',
                'published_date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),
                'source': 'Daily Mail',
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
            response = requests.get(self.base_url, headers=self.headers, timeout=5)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = []
            
            # Daily Mail 홈페이지에서 기사 링크 찾기
            selectors = [
                'h2 a[href*="/article-"]',
                'h3 a[href*="/article-"]',
                'a[href*="/article-"]'
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
                    
                    if href in found_urls:
                        continue
                    found_urls.add(href)
                    
                    # 이미지 추출
                    image_url = self._extract_dailymail_image(link, href)
                    if image_url:
                        if image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        elif image_url.startswith('/'):
                            image_url = self.base_url + image_url
                    
                    # Daily Mail 날짜 추출 개선
                    published_date = self._extract_dailymail_date(link, href)
                    
                    article = {
                        'title': title,
                        'url': href,
                        'summary': '',
                        'published_date': published_date,
                        'source': 'Daily Mail',
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
            elif '/business/' in url or '/money/' in url:
                return 'business'
            elif '/sport/' in url:
                return 'sports'
            elif '/tech/' in url or '/technology/' in url:
                return 'technology'
            elif '/travel/' in url:
                return 'travel'
            elif '/health/' in url:
                return 'health'
            elif '/showbiz/' in url or '/entertainment/' in url:
                return 'entertainment'
            else:
                return 'news'
        except:
            return 'news'
    
    def get_latest_news(self, category: str = 'news', limit: int = 10) -> List[Dict]:
        """카테고리별 최신 뉴스 가져오기"""
        return self._get_homepage_articles(limit) 