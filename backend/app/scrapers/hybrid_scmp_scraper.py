#!/usr/bin/env python3

"""
하이브리드 SCMP 스크래퍼
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

class HybridSCMPScraper:
    def __init__(self):
        self.base_url = "https://www.scmp.com"
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
        logger.info(f"SCMP 하이브리드 검색: {query}")
        
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
        """HTTP 기반 검색 (실제 SCMP 검색 URL 사용)"""
        try:
            # SCMP 검색 패턴들 (실제 작동 확인됨)
            if 'sport' in query.lower():
                # 스포츠 관련 검색은 topics/sports 사용
                search_patterns = [
                    f"https://www.scmp.com/topics/sports",
                    f"https://www.scmp.com/news?search={quote(query)}",
                    f"https://www.scmp.com/search/{quote(query)}"
                ]
            else:
                # 일반 검색
                search_patterns = [
                    f"https://www.scmp.com/news?search={quote(query)}",
                    f"https://www.scmp.com/search/{quote(query)}",
                    f"https://www.scmp.com/search?query={quote(query)}"
                ]
            
            for search_url in search_patterns:
                try:
                    logger.info(f"SCMP 검색 시도: {search_url}")
                    response = requests.get(search_url, headers=self.headers, timeout=10)
                    response.raise_for_status()
                    
                    extracted_articles = self._extract_scmp_search_results(response.text, limit, query)
                    if extracted_articles:
                        # 쿼리와 관련성이 높은 기사들만 필터링
                        relevant_articles = self._filter_relevant_articles(extracted_articles, query)
                        if relevant_articles:
                            logger.info(f"SCMP HTTP 검색 결과: {len(relevant_articles)}개 기사 찾음")
                            return relevant_articles
                except Exception as e:
                    logger.debug(f"SCMP 검색 URL 실패 {search_url}: {e}")
                    continue
            
            # 모든 검색 패턴 실패시
            logger.info("SCMP HTTP 검색 실패")
            return []
            
        except Exception as e:
            logger.debug(f"HTTP 검색 실패: {e}")
            return []
    
    def _extract_scmp_search_results(self, html_content: str, limit: int, query: str = '') -> List[Dict]:
        """SCMP 검색 결과에서 기사 추출 (개선된 파싱)"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # SCMP 기사 링크 패턴들 (테스트 확인됨)
            patterns = [
                'a[href*="/article/"]',
                'a[href*="scmp.com"]', 
                'a[href*="/news/"]'
            ]
            
            found_urls = set()
            
            for pattern in patterns:
                links = soup.select(pattern)
                
                for link in links:
                    try:
                        href = link.get('href', '')
                        title = link.get_text(strip=True)
                        
                        # URL 정규화
                        if href.startswith('/'):
                            href = self.base_url + href
                        elif not href.startswith('http'):
                            continue
                        
                        # 기본 검증
                        if (not title or len(title) < 15 or 
                            href in found_urls or 
                            'scmp.com' not in href):
                            continue
                        
                        found_urls.add(href)
                        
                        # SCMP 이미지 추출 - 개선된 방법
                        image_url = self._extract_scmp_image_improved(link, href)
                        
                        # SCMP 날짜 추출
                        published_date = self._extract_scmp_date(link, href)
                        
                        # 카테고리 추출
                        category = self._extract_category_from_url(href)
                        
                        article = {
                            'title': title,
                            'url': href,
                            'summary': '',  # 검색 결과에서는 요약 생략
                            'published_date': published_date,
                            'source': 'SCMP',
                            'category': category,
                            'scraped_at': datetime.now().isoformat(),
                            'relevance_score': 1,
                            'image_url': image_url
                        }
                        
                        articles.append(article)
                        
                        if len(articles) >= limit:
                            break
                            
                    except Exception as e:
                        logger.debug(f"SCMP 링크 파싱 실패: {e}")
                        continue
                
                if len(articles) >= limit:
                    break
                    
        except Exception as e:
            logger.error(f"SCMP 검색 결과 HTML 파싱 실패: {e}")
        
        return articles[:limit]
    
    def _filter_relevant_articles(self, articles: List[Dict], query: str) -> List[Dict]:
        """검색어와 관련성이 높은 기사들만 필터링"""
        if not query or not articles:
            return articles
        
        query_words = query.lower().split()
        relevant_articles = []
        
        for article in articles:
            title = article.get('title', '').lower()
            summary = article.get('summary', '').lower()
            
            # 관련성 점수 계산
            relevance_score = 0
            
            for word in query_words:
                # 제목에서 발견되면 높은 점수
                if word in title:
                    relevance_score += 3
                # 요약에서 발견되면 중간 점수
                elif word in summary:
                    relevance_score += 1
            
            # 관련성이 있는 기사만 포함
            if relevance_score > 0:
                article['relevance_score'] = relevance_score
                relevant_articles.append(article)
        
        # 관련성 점수로 정렬
        relevant_articles.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return relevant_articles
    
    def _extract_scmp_image_improved(self, link_elem, article_url: str) -> str:
        """개선된 SCMP 이미지 추출 - 메타 태그 우선"""
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
                
                # 기사 본문의 첫 번째 이미지
                article_img = soup.find('article')
                if article_img:
                    img = article_img.find('img')
                    if img and img.get('src'):
                        src = img['src']
                        if src.startswith('//'):
                            return 'https:' + src
                        elif src.startswith('/'):
                            return self.base_url + src
                        return src
                        
        except Exception as e:
            logger.debug(f"SCMP 메타 이미지 추출 실패: {e}")
        
        # 2. 폴백: 기존 방법 사용
        return self._extract_scmp_image(link_elem, article_url)
    
    def _extract_scmp_image(self, link_elem, article_url: str) -> str:
        """SCMP 기사에서 고유한 이미지 추출 (기존 로직)"""
        image_url = ''
        
        try:
            # 1. 링크 요소 자체에서 이미지 찾기
            img_elem = link_elem.find('img')
            if img_elem:
                for attr in ['src', 'data-src', 'data-lazy-src', 'data-original', 'data-img']:
                    img_src = img_elem.get(attr, '')
                    if img_src and self._is_valid_scmp_image(img_src):
                        image_url = img_src
                        break
            
            # 2. 링크의 직접 부모에서 이미지 찾기
            if not image_url:
                parent = link_elem.find_parent()
                if parent:
                    img_elems = parent.find_all('img')
                    for img_elem in img_elems:
                        for attr in ['src', 'data-src', 'data-lazy-src', 'data-original']:
                            img_src = img_elem.get(attr, '')
                            if img_src and self._is_valid_scmp_image(img_src):
                                image_url = img_src
                                break
                        if image_url:
                            break
            
            # 3. 형제 요소에서 이미지 찾기
            if not image_url:
                prev_sibling = link_elem.find_previous_sibling()
                next_sibling = link_elem.find_next_sibling()
                
                for sibling in [prev_sibling, next_sibling]:
                    if sibling and hasattr(sibling, 'find'):
                        img_elem = sibling.find('img')
                        if img_elem:
                            for attr in ['src', 'data-src', 'data-lazy-src']:
                                img_src = img_elem.get(attr, '')
                                if img_src and self._is_valid_scmp_image(img_src):
                                    image_url = img_src
                                    break
                        if image_url:
                            break
                
        except Exception as e:
            logger.debug(f"SCMP 이미지 추출 실패: {e}")
        
        return image_url
    
    def _is_valid_scmp_image(self, url: str) -> bool:
        """SCMP 이미지가 유효하고 고유한지 확인"""
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
            'scmp-logo',
            'facebook',
            'twitter',
            'linkedin',
            'whatsapp',
            'telegram',
            'instagram'
        ]
        
        url_lower = url.lower()
        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False
        
        # 유효한 이미지 확장자 확인
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        if any(ext in url_lower for ext in valid_extensions):
            return True
        
        # SCMP CDN 패턴 확인
        if any(domain in url for domain in ['scmp.com', 'scmpcdn.com', 'img.scmp.com']):
            return True
        
        return False
    
    def _extract_scmp_date(self, element, url: str) -> str:
        """SCMP 날짜 추출 (기존 로직)"""
        try:
            # 1. 요소에서 날짜 텍스트 찾기
            date_selectors = [
                '.published-date',
                '.date',
                '.timestamp',
                'time',
                '[datetime]',
                '.meta-date'
            ]
            
            for selector in date_selectors:
                date_elem = element.find(selector)
                if date_elem:
                    date_text = date_elem.get('datetime') or date_elem.get_text(strip=True)
                    if date_text:
                        return self._format_date(date_text)
            
            # 2. URL에서 날짜 패턴 찾기
            date_patterns = [
                r'/(\d{4})/(\d{1,2})/(\d{1,2})/',
                r'/article/(\d+)/',
                r'-(\d{4})-(\d{1,2})-(\d{1,2})'
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
            logger.debug(f"SCMP 날짜 추출 실패: {e}")
        
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
                '%m/%d/%Y'
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
                search_url = f"https://www.scmp.com/search?query={quote(query)}"
                driver.get(search_url)
                
                # JavaScript 로딩 대기
                time.sleep(5)
                
                # 검색 결과 찾기
                selectors = [
                    'article',
                    '[class*="article"]',
                    '[class*="story"]',
                    'a[href*="/news/"]',
                    'a[href*="/business/"]',
                    'a[href*="/sport/"]'
                ]
                
                for selector in selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        
                        for element in elements[:limit]:
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
            
            # SCMP 도메인 확인
            if 'scmp.com' not in url:
                return None
            
            return {
                'title': title[:200],
                'url': url,
                'summary': '',
                'published_date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),
                'source': 'SCMP',
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
            
            # SCMP 홈페이지에서 기사 링크 찾기
            selectors = [
                'h3 a[href*="/news/"]',
                'h2 a[href*="scmp.com"]',
                'a[href*="/article/"][href*="/"]',
                '.headline a',
                '.entry-title a',
                'h4 a[href*="/"]'
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
                    
                    if 'scmp.com' not in href or href in found_urls:
                        continue
                    found_urls.add(href)
                    
                    # 이미지 추출
                    image_url = self._extract_scmp_image(link, href)
                    if image_url:
                        if image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        elif image_url.startswith('/'):
                            image_url = self.base_url + image_url
                    
                    article = {
                        'title': title,
                        'url': href,
                        'summary': '',
                        'published_date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),
                        'source': 'SCMP',
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
            elif '/sport/' in url:
                return 'sports'
            elif '/tech/' in url or '/technology/' in url:
                return 'technology'
            elif '/lifestyle/' in url:
                return 'lifestyle'
            elif '/culture/' in url:
                return 'culture'
            elif '/opinion/' in url:
                return 'opinion'
            else:
                return 'General'
        except:
            return 'General'
    
    def get_latest_news(self, category: str = 'news', limit: int = 10) -> List[Dict]:
        """카테고리별 최신 뉴스 가져오기"""
        return self._get_homepage_articles(limit) 