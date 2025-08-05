# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import logging
from datetime import datetime, timedelta
import json
import re
import time

logger = logging.getLogger(__name__)

class BangkokPostScraper:
    """Bangkok Post 뉴스 스크래퍼 (www.bangkokpost.com)"""
    
    def __init__(self):
        self.base_url = "https://www.bangkokpost.com"
        self.search_url = "https://www.bangkokpost.com/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
    def search_news(self, query: str, limit: int = 10) -> List[Dict]:
        """Bangkok Post에서 뉴스 검색"""
        try:
            logger.info(f"Bangkok Post 검색: {query}")
            
            # Bangkok Post 검색 URL 패턴 (올바른 검색 도메인 사용)
            search_urls = [
                f"https://search.bangkokpost.com/search/result?category=all&q={query}",
                f"https://search.bangkokpost.com/search/result?q={query}",
                f"https://www.bangkokpost.com/search?q={query}",
                f"https://www.bangkokpost.com/search/result?q={query}",
                f"https://www.bangkokpost.com/?s={query}"
            ]
            
            for search_url in search_urls:
                try:
                    logger.info(f"Bangkok Post 검색 시도: {search_url}")
                    response = requests.get(search_url, headers=self.headers, timeout=15)
                    response.raise_for_status()
                    
                    articles = self._extract_search_results(response.text, limit, query)
                    if articles:
                        logger.info(f"Bangkok Post에서 {len(articles)}개 기사 발견")
                        return articles
                    else:
                        logger.debug(f"검색 결과 없음: {search_url}")
                        
                except Exception as e:
                    logger.debug(f"Bangkok Post 검색 URL 실패 {search_url}: {e}")
                    continue
            
            # 검색 실패 시 최신 뉴스로 대체
            logger.info("Bangkok Post 검색 실패, 최신 뉴스로 대체")
            return self.get_latest_news('news', limit)
            
        except Exception as e:
            logger.error(f"Bangkok Post 검색 실패: {e}")
            return []
    
    def _extract_search_results(self, html_content: str, limit: int, query: str = '') -> List[Dict]:
        """HTML에서 검색 결과 추출"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Bangkok Post 검색 결과 특화 구조 찾기
            article_selectors = [
                'h3',  # 방콕 포스트 검색 결과는 h3 태그에 있음
                '.col-md-12',  # 검색 결과 컨테이너
                '.search-result-item',
                'div[class*="search"]',
                'div[class*="result"]',
                'article',
                '.article',
                '.news-item',
                '.story',
                '.post'
            ]
            
            found_items = set()
            
            for selector in article_selectors:
                elements = soup.select(selector)
                if not elements:
                    continue
                    
                logger.debug(f"Bangkok Post {selector}: {len(elements)}개 요소 발견")
                
                for element in elements:
                    try:
                        # 방콕 포스트 특화 제목/URL 추출
                        title = ''
                        url = ''
                        
                        # h3 태그인 경우 (검색 결과 제목)
                        if element.name == 'h3':
                            link_elem = element.find('a', href=True)
                            if link_elem:
                                title = link_elem.get_text(strip=True)
                                url = link_elem.get('href')
                        else:
                            # 다른 컨테이너 내에서 h3 찾기
                            h3_elem = element.find('h3')
                            if h3_elem:
                                link_elem = h3_elem.find('a', href=True)
                                if link_elem:
                                    title = link_elem.get_text(strip=True)
                                    url = link_elem.get('href')
                            
                            # h3이 없으면 일반적인 방법으로 찾기
                            if not title:
                                title_selectors = ['h1', 'h2', 'h4', '.title', '.headline', 'a']
                                for title_sel in title_selectors:
                                    title_elem = element.find(title_sel)
                                    if title_elem:
                                        title = title_elem.get_text(strip=True)
                                        if len(title) > 15:
                                            break
                                
                                if not url:
                                    link_elem = element.find('a', href=True)
                                    if link_elem:
                                        url = link_elem.get('href')
                        
                        if not title or len(title) < 15:
                            continue
                        
                        # 방콕 포스트 tracking URL 처리
                        if url and 'track/visitAndRedirect' in url:
                            # URL에서 실제 주소 추출
                            import urllib.parse
                            if 'href=' in url:
                                actual_url = url.split('href=')[1].split('&')[0]
                                url = urllib.parse.unquote(actual_url)
                        
                        # URL 정규화
                        if url and not url.startswith('http'):
                            if url.startswith('/'):
                                url = self.base_url + url
                            else:
                                url = self.base_url + '/' + url
                        
                        if not url or 'bangkokpost.com' not in url:
                            continue
                        
                        # 중복 확인
                        if url in found_items:
                            continue
                        found_items.add(url)
                        
                        # 방콕 포스트 요약 찾기
                        summary = ''
                        
                        # h3 태그인 경우, 다음 형제 요소들에서 요약 찾기
                        if element.name == 'h3':
                            next_element = element.find_next_sibling()
                            while next_element and not summary:
                                if next_element.name == 'p':
                                    sum_text = next_element.get_text(strip=True)
                                    # 날짜나 메타 정보 제외하고 실제 기사 내용만
                                    # » 기호로 시작하는 요약문은 포함
                                    if sum_text.startswith('»'):
                                        sum_text = sum_text[1:].strip()  # » 기호 제거
                                    
                                    if (len(sum_text) > 50 and 
                                        not sum_text.startswith('Published on') and
                                        'bangkokpost.com' not in sum_text.lower() and
                                        not sum_text.startswith('Bangkok')):
                                        summary = sum_text
                                        break
                                next_element = next_element.find_next_sibling()
                        else:
                            # 일반적인 요약 찾기
                            summary_selectors = ['p', '.excerpt', '.summary', '.description', '.lead', '.intro']
                            
                            for sum_sel in summary_selectors:
                                sum_elem = element.find(sum_sel)
                                if sum_elem:
                                    sum_text = sum_elem.get_text(strip=True)
                                    if (len(sum_text) > 30 and 
                                        not sum_text.startswith('Bangkok') and
                                        not sum_text.startswith('Published on')):
                                        summary = sum_text
                                        break
                        
                        # 방콕 포스트 이미지 추출
                        image_url = self._extract_bangkokpost_image(element, url)
                        
                        # 날짜 추출
                        published_date = self._extract_date(element, url)
                        
                        # 카테고리 추출
                        category = self._extract_category_from_url(url)
                        
                        article = {
                            'title': title,
                            'url': url,
                            'summary': summary[:300] if summary else title[:200],
                            'published_date': published_date,
                            'source': 'Bangkok Post',
                            'category': category,
                            'scraped_at': datetime.now().isoformat(),
                            'relevance_score': 1,
                            'image_url': image_url or self._get_fallback_image(category)
                        }
                        
                        articles.append(article)
                        
                        if len(articles) >= limit:
                            break
                            
                    except Exception as e:
                        logger.debug(f"Bangkok Post 기사 파싱 실패: {e}")
                        continue
                
                if len(articles) >= limit:
                    break
                    
        except Exception as e:
            logger.error(f"Bangkok Post HTML 파싱 실패: {e}")
        
        return articles[:limit]
    
    def _extract_date(self, element, url: str) -> str:
        """요소나 URL에서 날짜 추출"""
        try:
            # 요소에서 날짜 패턴 찾기
            text = element.get_text()
            
            # 다양한 날짜 패턴
            date_patterns = [
                r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
                r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
                r'\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}',
                r'(\d{1,2}\s+hours?\s+ago)',
                r'(\d{1,2}\s+days?\s+ago)'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        date_str = match.group(0)
                        
                        # "X hours ago" 형태 처리
                        if 'hours ago' in date_str.lower():
                            hours = int(re.search(r'\d+', date_str).group())
                            date_obj = datetime.now() - timedelta(hours=hours)
                            return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                        
                        # "X days ago" 형태 처리
                        elif 'days ago' in date_str.lower():
                            days = int(re.search(r'\d+', date_str).group())
                            date_obj = datetime.now() - timedelta(days=days)
                            return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                        
                        # 일반 날짜 파싱
                        for fmt in ['%m/%d/%Y', '%m-%d-%Y', '%Y/%m/%d', '%Y-%m-%d', '%B %d, %Y', '%d %b %Y']:
                            try:
                                date_obj = datetime.strptime(date_str, fmt)
                                return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                            except:
                                continue
                    except:
                        continue
            
            # URL에서 날짜 추출
            url_date_match = re.search(r'/(\d{4})/(\d{1,2})/(\d{1,2})/', url)
            if url_date_match:
                year, month, day = url_date_match.groups()
                date_obj = datetime(int(year), int(month), int(day))
                return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
            
        except Exception as e:
            logger.debug(f"Bangkok Post 날짜 추출 실패: {e}")
        
        # 기본값: 현재 시간
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    def _extract_bangkokpost_image(self, element, url: str) -> str:
        """방콕 포스트 기사에서 이미지 추출 또는 기본 이미지 제공"""
        image_url = ''
        
        try:
            # 1. 요소에서 이미지 찾기
            img_elem = element.find('img')
            if img_elem:
                potential_imgs = [
                    img_elem.get('src', ''),
                    img_elem.get('data-src', ''),
                    img_elem.get('data-lazy-src', ''),
                    img_elem.get('data-original', '')
                ]
                
                for img_src in potential_imgs:
                    if img_src and self._is_valid_bangkokpost_image(img_src):
                        image_url = img_src
                        break
            
            # 2. 주변 요소에서 이미지 찾기
            if not image_url:
                # 형제 요소들에서 이미지 찾기
                siblings = [element.find_previous_sibling(), element.find_next_sibling()]
                for sibling in siblings:
                    if sibling and hasattr(sibling, 'find'):
                        img_elem = sibling.find('img')
                        if img_elem:
                            for attr in ['src', 'data-src', 'data-lazy-src']:
                                img_src = img_elem.get(attr, '')
                                if img_src and self._is_valid_bangkokpost_image(img_src):
                                    image_url = img_src
                                    break
                        if image_url:
                            break
            
            # 3. URL 정규화
            if image_url:
                if not image_url.startswith('http'):
                    if image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    elif image_url.startswith('/'):
                        image_url = self.base_url + image_url
            
            # 4. 실제 기사 페이지에서 이미지 추출 시도
            if not image_url:
                image_url = self._extract_image_from_article_page(url)
                
        except Exception as e:
            logger.debug("방콕 포스트 이미지 추출 실패: {}".format(e))
        
        return image_url
    
    def _extract_image_from_article_page(self, article_url: str) -> str:
        """실제 기사 페이지에서 메인 이미지 추출"""
        try:
            response = requests.get(article_url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Bangkok Post 기사 페이지의 메인 이미지 찾기
                selectors = [
                    'meta[property="og:image"]',
                    'meta[name="twitter:image"]',
                    '.story-image img',
                    '.article-image img', 
                    '.hero-image img',
                    'figure img',
                    '.main-image img',
                    'img[src*="static.bangkokpost.com"]'
                ]
                
                for selector in selectors:
                    elem = soup.select_one(selector)
                    if elem:
                        img_url = elem.get('content') or elem.get('src') or elem.get('data-src')
                        if img_url and self._is_valid_bangkokpost_article_image(img_url):
                            # URL 정규화
                            if not img_url.startswith('http'):
                                if img_url.startswith('//'):
                                    img_url = 'https:' + img_url
                                elif img_url.startswith('/'):
                                    img_url = self.base_url + img_url
                            return img_url
                            
        except Exception as e:
            logger.debug("기사 페이지에서 이미지 추출 실패: {}".format(e))
        
        return ''
    
    def _is_valid_bangkokpost_article_image(self, url: str) -> bool:
        """기사 페이지에서 추출한 이미지가 유효한 실제 이미지인지 확인 (개선됨)"""
        if not url:
            return False
        
        # 데이터 URL과 blob URL 제외
        if url.startswith('data:') or url.startswith('blob:'):
            return False
        
        url_lower = url.lower()
        
        # 더 구체적인 제외 패턴 - 명확한 UI 요소만 제외
        exclude_patterns = [
            'bp-business.png', 'bp-news.png', 'bp-sports.png', 'bp-tech.png',
            'bangkokpost-logo', 'logo-bangkokpost',
            'favicon.ico', 'favicon.png',
            'alert.svg', 'icon-close.svg', 'icon-arrow',
            'placeholder-image', 'no-image', 'default-image'
        ]
        
        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False
        
        # 크기 제한 - 너무 작은 이미지 (UI 아이콘일 가능성) 제외
        size_indicators = ['16x16', '24x24', '32x32', '48x48', '64x64']
        if any(size in url_lower for size in size_indicators):
            return False
        
        # 유효한 이미지 패턴 - 더 포괄적으로
        valid_patterns = [
            '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.svg',
            'bangkokpost.com',
            'static.bangkokpost.com', 
            'cdn.bangkokpost.com',
            'media.bangkokpost.com',
            '/image/', '/images/', '/photo/', '/photos/', '/pictures/', '/media/',
            '/uploads/', '/wp-content/', '/assets/', '/content/'
        ]
        
        # 최소 길이 확인 - 너무 짧은 URL은 보통 아이콘
        if len(url) > 20:
            return any(pattern in url_lower for pattern in valid_patterns)
        
        return False
    
    def _is_valid_bangkokpost_image(self, url: str) -> bool:
        """방콕 포스트 이미지 URL이 유효한지 확인 (개선됨)"""
        if not url:
            return False
        
        # 데이터 URL과 빈 이미지 제외
        if url.startswith('data:') or url.startswith('blob:'):
            return False
        
        url_lower = url.lower()
        
        # 더 관대한 제외 패턴 - 명확한 로고/아이콘만 제외
        exclude_patterns = [
            'logo.png', 'logo.jpg', 'logo.svg',
            'favicon.ico', 'favicon.png',
            'sprite.png', 'sprite.jpg',
            'blank.gif', 'transparent.gif',
            '/icons/small/', '/icons/tiny/'
        ]
        
        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False
        
        # 유효한 이미지 패턴 - 더 포괄적으로 수정
        valid_patterns = [
            '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.svg',
            'bangkokpost.com',
            'static.bangkokpost.com', 
            'cdn.bangkokpost.com',
            '/image/', '/images/', '/photo/', '/photos/', '/media/',
            '/uploads/', '/wp-content/uploads/'
        ]
        
        return any(pattern in url_lower for pattern in valid_patterns)
    
    def _extract_category_from_url(self, url: str) -> str:
        """URL에서 카테고리 추출 (표준화됨)"""
        try:
            if not url:
                return 'news'
                
            url_lower = url.lower()
            
            # 우선순위 기반 카테고리 매핑 (표준 카테고리로 통일)
            category_patterns = [
                # 비즈니스/경제 (높은 우선순위)
                ('/business/', 'business'),
                ('/economy/', 'business'),
                ('/finance/', 'business'),
                ('/market/', 'business'),
                
                # 스포츠 (높은 우선순위)
                ('/sports/', 'sports'),
                ('/sport/', 'sports'),
                
                # 기술
                ('/tech/', 'technology'),
                ('/technology/', 'technology'),
                
                # 엔터테인먼트
                ('/arts-and-entertainment/', 'entertainment'),
                ('/entertainment/', 'entertainment'),
                
                # 라이프스타일
                ('/life/', 'lifestyle'),
                ('/lifestyle/', 'lifestyle'),
                ('/social-and-lifestyle/', 'lifestyle'),
                ('/travel/', 'lifestyle'),  # 여행을 라이프스타일로 분류
                
                # 정치 (키워드 기반)
                ('/politics/', 'politics'),
                
                # 국제
                ('/world/', 'world'),
                
                # 의견
                ('/opinion/', 'opinion'),
                
                # 기타
                ('/auto/', 'lifestyle'),
                ('/learning/', 'education'),
                ('/education/', 'education'),
                
                # 지역 뉴스 (낮은 우선순위)
                ('/thailand/', 'news'),
            ]
            
            # 우선순위에 따라 매칭
            for pattern, category in category_patterns:
                if pattern in url_lower:
                    return category
            
            # 키워드 기반 추가 분류
            if any(word in url_lower for word in ['politic', 'government', 'minister', 'election']):
                return 'politics'
            elif any(word in url_lower for word in ['health', 'medical', 'hospital']):
                return 'health'
            
            return 'news'  # 기본값
        except:
            return 'news'
    
    def get_latest_news(self, category: str = 'news', limit: int = 10) -> List[Dict]:
        """Bangkok Post 최신 뉴스 가져오기"""
        try:
            # 카테고리별 URL 매핑 (실제 Bangkok Post 구조에 맞게 수정)
            category_urls = {
                'all': self.base_url,
                'news': f"{self.base_url}/thailand",
                'business': f"{self.base_url}/business",
                'sports': f"{self.base_url}/sports",
                'sport': f"{self.base_url}/sports", 
                'tech': f"{self.base_url}/life/tech",
                'technology': f"{self.base_url}/life/tech",
                'world': f"{self.base_url}/world",
                'travel': f"{self.base_url}/life/travel",
                'lifestyle': f"{self.base_url}/life/social-and-lifestyle",
                'entertainment': f"{self.base_url}/life/arts-and-entertainment",
                'opinion': f"{self.base_url}/opinion"
            }
            
            # Bangkok Post는 메인 페이지만 안정적으로 작동하므로 메인 페이지 우선 사용
            # 메인 페이지에는 모든 카테고리의 기사가 포함되어 있음
            url_priority = [
                self.base_url,  # 메인 페이지 (가장 안정적)
            ]
            
            # 요청된 카테고리가 있으면 해당 URL도 시도해보지만 실패해도 괜찮음
            if category != 'all':
                category_url = category_urls.get(category)
                if category_url and category_url != self.base_url:
                    url_priority.insert(0, category_url)  # 먼저 시도하되 실패하면 메인으로
            
            for url in url_priority:
                try:
                    # 메인 페이지가 아닌 경우 더 짧은 타임아웃 사용
                    timeout = 10 if url != self.base_url else 20
                    logger.info(f"Bangkok Post 최신 뉴스 시도: {url} (timeout: {timeout}s)")
                    
                    response = requests.get(url, headers=self.headers, timeout=timeout)
                    if response.status_code == 200:
                        # 실제 웹사이트 구조에 맞게 기사 추출
                        articles = self._extract_bangkokpost_articles(response.text, limit, category)
                        if articles:
                            logger.info(f"Bangkok Post {url}에서 {len(articles)}개 기사 수집 성공")
                            return articles
                        else:
                            logger.debug(f"Bangkok Post {url}에서 기사 추출 실패")
                    else:
                        logger.debug(f"Bangkok Post {url} 응답 코드: {response.status_code}")
                
                except requests.exceptions.Timeout:
                    logger.debug(f"Bangkok Post {url} 타임아웃 (timeout: {timeout}s)")
                    continue
                except Exception as e:
                    logger.debug(f"Bangkok Post {url} 오류: {e}")
                    continue
            
            logger.warning("Bangkok Post 모든 URL 시도 실패")
            return []
            
        except Exception as e:
            logger.error(f"Bangkok Post 최신 뉴스 가져오기 실패: {e}")
            return []
    
    def _extract_bangkokpost_articles(self, html_content: str, limit: int, category: str = '') -> List[Dict]:
        """Bangkok Post 웹사이트 구조에 맞게 기사 추출"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Bangkok Post 실제 기사 선택자들 (테스트로 확인된 패턴)
            article_selectors = [
                # 가장 효과적인 패턴들 (테스트로 확인됨)
                'h3 a[href*="/thailand/"]',
                'h3 a[href*="/business/"]',
                'h3 a[href*="/world/"]',
                'h3 a[href*="/news/"]',
                'h3 a[href*="/sports/"]',
                'h2 a[href*="/thailand/"]',
                'h2 a[href*="/business/"]',
                'h1 a[href*="/thailand/"]',
                # 일반적인 기사 링크들
                'a[href*="bangkokpost.com/thailand/"]',
                'a[href*="bangkokpost.com/business/"]',
                'a[href*="bangkokpost.com/world/"]',
                'a[href*="bangkokpost.com/news/"]'
            ]
            
            found_urls = set()
            
            for selector in article_selectors:
                try:
                    links = soup.select(selector)
                    logger.debug(f"Bangkok Post {selector}: {len(links)}개 링크 발견")
                    
                    for link in links:
                        try:
                            title = link.get_text(strip=True)
                            url = link.get('href', '')
                            
                            # 기본 검증
                            if not title or len(title) < 10:
                                continue
                                
                            if not url:
                                continue
                                
                            # URL 정규화
                            if not url.startswith('http'):
                                if url.startswith('/'):
                                    url = self.base_url + url
                                else:
                                    url = self.base_url + '/' + url
                            
                            # Bangkok Post URL 확인 및 유효한 기사 경로인지 확인
                            if ('bangkokpost.com' not in url or 
                                not any(section in url for section in ['/thailand/', '/business/', '/world/', '/news/', '/sports/', '/life/']) or
                                any(invalid in url for invalid in ['/campaign', '/topics', '/archive', '/multimedia'])):
                                continue
                            
                            # 중복 확인
                            if url in found_urls:
                                continue
                            found_urls.add(url)
                            
                            # 불필요한 링크 필터링
                            if any(skip in url.lower() for skip in [
                                '/search', '/login', '/register', '/subscribe', 
                                '/contact', '/about', '/terms', '/privacy', '/archive',
                                'facebook.com', 'twitter.com', 'instagram.com'
                            ]):
                                continue
                                
                            # 너무 짧은 제목이나 카테고리 이름만 있는 것 제외
                            if len(title) < 10 or title.lower() in [
                                'news', 'business', 'world', 'thailand', 'sports', 'life',
                                'general', 'politics', 'crime', 'special reports'
                            ]:
                                continue
                                
                            # 네비게이션 링크들과 섹션 이름들 제외 (더 간단하게)
                            nav_words = ['home', 'search', 'subscribe', 'login', 'register', 'contact', 'about']
                            if any(nav in title.lower() for nav in nav_words):
                                continue
                            
                            # 요약과 이미지 추출을 위해 링크의 부모 요소 찾기
                            parent = link.parent
                            if parent:
                                # 부모의 부모까지 확인
                                grand_parent = parent.parent
                                context = grand_parent if grand_parent else parent
                            else:
                                context = link
                            
                            # 요약 추출
                            summary = self._extract_bangkokpost_summary(context, title)
                            
                            # 이미지 추출
                            image_url = self._extract_bangkokpost_image(context, url)
                            
                            # 날짜 추출
                            published_date = self._extract_bangkokpost_date(context, url)
                            
                            # 카테고리 추출
                            article_category = self._extract_category_from_url(url) or category
                            
                            # 특정 카테고리가 요청된 경우 필터링 (all이 아닌 경우)
                            if (category and category != 'all' and category != 'news' and 
                                article_category != category):
                                # sports나 business 등 특정 카테고리가 요청됐는데 다른 카테고리면 스킵
                                continue
                            
                            article = {
                                'title': title,
                                'url': url,
                                'summary': summary[:300] if summary else title[:200],
                                'published_date': published_date,
                                'source': 'Bangkok Post',
                                'category': article_category,
                                'scraped_at': datetime.now().isoformat(),
                                'relevance_score': 1,
                                'image_url': image_url or self._get_fallback_image(article_category)
                            }
                            
                            articles.append(article)
                            
                            if len(articles) >= limit:
                                break
                                
                        except Exception as e:
                            logger.debug(f"Bangkok Post 개별 기사 처리 실패: {e}")
                            continue
                    
                    if len(articles) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug(f"Bangkok Post selector {selector} 처리 실패: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Bangkok Post HTML 파싱 실패: {e}")
        
        # 결과 검증 및 정렬
        valid_articles = []
        for article in articles:
            # 최종 검증
            if (article['title'] and len(article['title']) >= 15 and
                article['url'] and 'bangkokpost.com' in article['url']):
                valid_articles.append(article)
        
        return valid_articles[:limit]
    
    def _extract_bangkokpost_summary(self, element, title: str) -> str:
        """Bangkok Post 기사에서 요약 추출"""
        summary = ''
        
        try:
            # 다양한 요약 패턴 찾기
            summary_selectors = [
                'p',  # 일반적인 단락
                '.excerpt',
                '.summary', 
                '.description',
                '.lead',
                '.intro'
            ]
            
            for selector in summary_selectors:
                elements = element.find_all(selector) if hasattr(element, 'find_all') else []
                
                for elem in elements:
                    text = elem.get_text(strip=True)
                    
                    # 유효한 요약인지 확인
                    if (len(text) > 30 and len(text) < 500 and
                        text != title and
                        not text.startswith('Bangkok Post') and
                        not text.startswith('Published on') and
                        not text.lower().startswith('click here') and
                        not text.lower().startswith('read more') and
                        'bangkokpost.com' not in text.lower()):
                        
                        summary = text
                        break
                
                if summary:
                    break
                    
        except Exception as e:
            logger.debug(f"Bangkok Post 요약 추출 실패: {e}")
        
        return summary
    
    def _extract_bangkokpost_date(self, element, url: str) -> str:
        """Bangkok Post 기사에서 날짜 추출"""
        try:
            # 요소에서 날짜 찾기
            if hasattr(element, 'get_text'):
                text = element.get_text()
                
                # Bangkok Post 날짜 패턴들
                date_patterns = [
                    r'(\d{1,2}\s+Jul\s+2025)',  # "17 Jul 2025" 형태
                    r'(\d{1,2}\s+\w{3}\s+\d{4})',  # "17 Jul 2025" 일반화
                    r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
                    r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})'
                ]
                
                for pattern in date_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        date_str = match.group(0)
                        try:
                            # 여러 날짜 형식 시도
                            for fmt in ['%d %b %Y', '%d %B %Y', '%m/%d/%Y', '%m-%d-%Y', '%Y/%m/%d', '%Y-%m-%d']:
                                try:
                                    date_obj = datetime.strptime(date_str, fmt)
                                    return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                                except:
                                    continue
                        except:
                            continue
            
            # URL에서 날짜 추출 시도
            url_date_match = re.search(r'/(\d{4})/(\d{1,2})/(\d{1,2})/', url)
            if url_date_match:
                year, month, day = url_date_match.groups()
                date_obj = datetime(int(year), int(month), int(day))
                return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                
        except Exception as e:
            logger.debug(f"Bangkok Post 날짜 추출 실패: {e}")
        
        # 기본값: 현재 시간
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT') 