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
        self.search_url = "https://nypost.com/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
    def search_news(self, query: str, limit: int = 10) -> List[Dict]:
        """NY Post에서 뉴스 검색"""
        try:
            logger.info(f"NY Post 검색: {query}")
            
            # 올바른 검색 URL 패턴 사용
            search_urls = [
                f"https://nypost.com/search/{query}/"
            ]
            
            for search_url in search_urls:
                try:
                    logger.info(f"시도 중: {search_url}")
                    response = requests.get(search_url, headers=self.headers, timeout=15)
                    response.raise_for_status()
                    
                    # 페이지에 검색어나 관련 콘텐츠가 있는지 확인
                    page_text = response.text.lower()
                    if query.lower() in page_text or 'search' in page_text:
                        logger.info(f"검색 결과 발견: {search_url}")
                        articles = self._extract_search_results(response.text, limit, query)
                        if articles:
                            logger.info(f"NY Post에서 {len(articles)}개 검색 결과 찾음")
                            return articles
                    else:
                        logger.debug(f"검색 결과 없음: {search_url}")
                        
                except Exception as e:
                    logger.debug(f"검색 URL 실패 {search_url}: {e}")
                    continue
            
            # 모든 검색 방식이 실패하면 카테고리별 최신 뉴스 반환
            logger.info("검색 실패, 최신 뉴스로 대체")
            return self.get_latest_news('news', limit)
            
        except Exception as e:
            logger.error(f"NY Post 검색 실패: {e}")
            return []
    
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