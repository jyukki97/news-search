# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import logging
from datetime import datetime
import json
import re

logger = logging.getLogger(__name__)

class NYPostScraper:
    """New York Post 뉴스 스크래퍼"""
    
    def __init__(self):
        self.base_url = "https://nypost.com"
        self.search_url = "https://nypost.com/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
    def search_news(self, query: str, limit: int = 10) -> List[Dict]:
        """NY Post에서 뉴스 검색 (최신 뉴스로 대체)"""
        try:
            logger.info(f"NY Post 검색: {query} (최신 뉴스 방식)")
            
            # 간단하게 최신 뉴스를 가져오는 방식 사용
            response = requests.get(self.base_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            articles = self._extract_articles_from_homepage(response.text, limit)
            if articles:
                logger.info(f"NY Post에서 {len(articles)}개 최신 뉴스 찾음")
                return articles
            else:
                logger.warning("NY Post 홈페이지에서 기사를 찾을 수 없음")
                return []
            
        except Exception as e:
            logger.error(f"NY Post 접근 실패: {e}")
            return []
    
    def _extract_articles_from_homepage(self, html_content: str, limit: int) -> List[Dict]:
        """NY Post 홈페이지에서 기사 추출 - 단순화된 방식"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 홈페이지의 기사 링크들 찾기
            article_links = []
            
            # 다양한 기사 링크 선택자 시도
            selectors = [
                'h3 a[href*="/20"]',  # 날짜가 포함된 링크
                'h2 a[href*="nypost.com"]',  # nypost.com이 포함된 링크
                'a[href*="/20"][href*="/"]',  # 연도와 슬래시가 포함된 링크
                '.entry-title a',  # 제목 링크
                '.headline a'  # 헤드라인 링크
            ]
            
            for selector in selectors:
                links = soup.select(selector)
                article_links.extend(links)
                if len(article_links) >= limit * 2:  # 충분한 링크가 있으면 중단
                    break
            
            found_urls = set()
            
            for link in article_links:
                try:
                    href = link.get('href', '')
                    title = link.get_text(strip=True)
                    
                    # URL 검증 및 정규화
                    if not href or not title or len(title) < 10:
                        continue
                    
                    if href.startswith('/'):
                        href = self.base_url + href
                    elif not href.startswith('http'):
                        continue
                    
                    if 'nypost.com' not in href:
                        continue
                    
                    # 중복 제거
                    if href in found_urls:
                        continue
                    found_urls.add(href)
                    
                    # 이미지 추출 - 링크 주변에서 이미지 찾기
                    image_url = ''
                    
                    # 1. 링크의 부모 컨테이너에서 이미지 찾기
                    parent = link.find_parent()
                    while parent and not image_url:
                        img_elem = parent.find('img')
                        if img_elem:
                            # 다양한 이미지 속성 확인
                            for attr in ['src', 'data-src', 'data-lazy-src', 'data-original', 'data-img']:
                                img_src = img_elem.get(attr, '')
                                if img_src and self._is_valid_image_url(img_src):
                                    image_url = img_src
                                    break
                        parent = parent.find_parent()
                        # 너무 많이 올라가지 않도록 제한
                        if parent and parent.name in ['body', 'html']:
                            break
                    
                    # 2. 링크 근처의 형제 요소에서 이미지 찾기
                    if not image_url:
                        siblings = [link.find_previous_sibling(), link.find_next_sibling()]
                        for sibling in siblings:
                            if sibling:
                                img_elem = sibling.find('img') if hasattr(sibling, 'find') else None
                                if img_elem:
                                    for attr in ['src', 'data-src', 'data-lazy-src', 'data-original']:
                                        img_src = img_elem.get(attr, '')
                                        if img_src and self._is_valid_image_url(img_src):
                                            image_url = img_src
                                            break
                                if image_url:
                                    break
                    
                    # 이미지 URL 정규화
                    if image_url:
                        if image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        elif image_url.startswith('/'):
                            image_url = self.base_url + image_url
                        elif not image_url.startswith('http'):
                            image_url = self.base_url + '/' + image_url
                    
                    # 기본 기사 정보 생성
                    article = {
                        'title': title,
                        'url': href,
                        'summary': '',
                        'published_date': '',
                        'source': 'NY Post',
                        'category': self._extract_category_from_url(href),
                        'scraped_at': datetime.now().isoformat(),
                        'relevance_score': 1,
                        'image_url': image_url
                    }
                    
                    articles.append(article)
                    
                    if len(articles) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug(f"NY Post 홈페이지 링크 파싱 실패: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"NY Post 홈페이지 HTML 파싱 실패: {e}")
        
        return articles[:limit]
    
    def _is_valid_image_url(self, url: str) -> bool:
        """이미지 URL이 유효한지 확인"""
        if not url:
            return False
        
        # 기본 필터링
        if url.startswith('data:') or 'placeholder' in url.lower() or 'logo' in url.lower():
            return False
        
        # 이미지 확장자 확인
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
        url_lower = url.lower()
        
        # URL에 이미지 확장자가 있는지 확인
        has_extension = any(ext in url_lower for ext in valid_extensions)
        
        # 또는 이미지 관련 단어가 포함되어 있는지 확인
        image_keywords = ['image', 'img', 'photo', 'picture', 'thumb']
        has_keyword = any(keyword in url_lower for keyword in image_keywords)
        
        return has_extension or has_keyword
    
    def _extract_search_results(self, html_content: str, limit: int, query: str = '') -> List[Dict]:
        """HTML에서 검색 결과 추출 - NY Post 검색 페이지 구조에 맞게 최적화"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # NY Post 검색 결과의 실제 구조 확인
            # H3 제목을 가진 기사들 찾기
            h3_titles = soup.find_all('h3')
            
            found_items = set()  # 중복 제거용
            
            for h3 in h3_titles:
                try:
                    # 제목 추출
                    title = h3.get_text(strip=True)
                    if not title or len(title) < 10:
                        continue
                    
                    # 제목에서 URL 찾기 (H3 안의 링크 또는 인근 링크)
                    url = ''
                    title_link = h3.find('a')
                    if title_link and title_link.get('href'):
                        url = title_link.get('href')
                    else:
                        # H3 주변에서 링크 찾기
                        parent = h3.find_parent()
                        if parent:
                            nearby_link = parent.find('a', href=True)
                            if nearby_link:
                                url = nearby_link.get('href')
                    
                    # URL 정규화
                    if url and not url.startswith('http'):
                        if url.startswith('/'):
                            url = 'https://nypost.com' + url
                        else:
                            url = 'https://nypost.com/' + url
                    
                    if not url or 'nypost.com' not in url:
                        continue
                    
                    # 중복 확인
                    if url in found_items:
                        continue
                    found_items.add(url)
                    
                    # H3 다음 요소들에서 메타데이터와 요약 찾기
                    summary = ''
                    published_date = ''
                    author = ''
                    image_url = ''
                    
                    # H3의 부모 컨테이너에서 정보 추출
                    container = h3.find_parent()
                    if container:
                        # 작성자와 날짜 정보 찾기 (By [Author] [Date] 패턴)
                        for text_elem in container.find_all(text=True):
                            text = text_elem.strip()
                            if text.startswith('By ') and ('|' in text or ',' in text):
                                # "By Lori A Bashian, Fox News July 15, 2025 | 2:41am" 형태 파싱
                                try:
                                    parts = text.split('|')[0].strip()  # 시간 부분 제거
                                    if 'By ' in parts:
                                        author_part = parts.split('By ')[1].strip()
                                        # 날짜 패턴 찾기
                                        import re
                                        date_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}', author_part)
                                        if date_match:
                                            published_date = date_match.group(0)
                                            author = author_part.replace(published_date, '').strip().rstrip(',').strip()
                                        else:
                                            author = author_part
                                except:
                                    pass
                                break
                        
                        # 요약 텍스트 찾기 (H3 다음의 텍스트)
                        next_sibling = h3.find_next_sibling()
                        while next_sibling and not summary:
                            if next_sibling.name and next_sibling.get_text(strip=True):
                                text = next_sibling.get_text(strip=True)
                                # 작성자/날짜 정보가 아닌 실제 요약인지 확인
                                if not text.startswith('By ') and len(text) > 20 and not text.startswith('###'):
                                    summary = text
                                    break
                            next_sibling = next_sibling.find_next_sibling()
                        
                        # 이미지 찾기
                        img_elem = container.find('img')
                        if img_elem:
                            image_url = img_elem.get('src', '') or img_elem.get('data-src', '') or img_elem.get('data-lazy-src', '')
                    
                    # 기본 검증
                    if not title or len(title) < 10:
                        continue
                    
                    # URL 정규화
                    if url.startswith('/'):
                        url = self.base_url + url
                    
                    # 이미지 URL 정규화
                    if image_url and not image_url.startswith('http'):
                        if image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        elif image_url.startswith('/'):
                            image_url = self.base_url + image_url
                    
                    # 중복 체크 (제목 기반)
                    if title in found_items:
                        continue
                    found_items.add(title)
                    
                    # 날짜 추출
                    published_date = self._extract_date(url, summary)
                    
                    article = {
                        'title': title,
                        'url': url,
                        'summary': summary[:300] if summary else '',
                        'published_date': published_date,
                        'source': 'NY Post',
                        'category': self._extract_category_from_url(url),
                        'scraped_at': datetime.now().isoformat(),
                        'relevance_score': 1,
                        'image_url': image_url
                    }
                    
                    articles.append(article)
                    
                    if len(articles) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug(f"NY Post 링크 파싱 실패: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"NY Post HTML 파싱 실패: {e}")
        
        return articles[:limit]
    
    def _extract_date(self, url: str, text: str) -> str:
        """URL이나 텍스트에서 날짜 추출"""
        try:
            # URL에서 날짜 패턴 찾기 (예: /2024/01/15/)
            date_pattern = r'/(\d{4})/(\d{1,2})/(\d{1,2})/'
            match = re.search(date_pattern, url)
            if match:
                year, month, day = match.groups()
                date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
            
            # 텍스트에서 날짜 패턴 찾기
            text_date_patterns = [
                r'(\w+\s+\d{1,2},\s+\d{4})',  # January 15, 2024
                r'(\d{1,2}/\d{1,2}/\d{4})',   # 1/15/2024
                r'(\d{4}-\d{2}-\d{2})',       # 2024-01-15
            ]
            
            for pattern in text_date_patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(1)
                    
        except Exception as e:
            logger.debug(f"날짜 추출 실패: {e}")
        
        return ''
    
    def _extract_category_from_url(self, url: str) -> str:
        """URL에서 카테고리 추출"""
        categories = {
            '/sports/': 'sports',
            '/business/': 'business',
            '/politics/': 'politics',
            '/entertainment/': 'entertainment',
            '/tech/': 'technology',
            '/health/': 'health',
            '/opinion/': 'opinion',
            '/world/': 'world',
            '/metro/': 'metro'
        }
        
        for path, category in categories.items():
            if path in url:
                return category
        
        return 'news'
    
    def get_latest_news(self, category: str = 'news', limit: int = 10) -> List[Dict]:
        """카테고리별 최신 뉴스"""
        # 카테고리에 맞는 키워드로 검색하거나 특정 페이지 접근
        category_keywords = {
            'news': 'breaking news',
            'sports': 'sports',
            'business': 'business',
            'politics': 'politics',
            'entertainment': 'entertainment',
            'technology': 'tech',
            'health': 'health'
        }
        
        keyword = category_keywords.get(category, 'news')
        return self.search_news(keyword, limit) 