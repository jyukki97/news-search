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
            
            # 여러 검색 URL 패턴 시도
            search_urls = [
                f"https://nypost.com/search/{query}/",
                f"https://nypost.com/?s={query}",
                f"https://nypost.com/search?q={query}",
                f"https://nypost.com/tag/{query}/"
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
        """HTML에서 검색 결과 추출"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 검색 결과인지 확인
            page_text = soup.get_text().lower()
            is_search_page = query.lower() in page_text if query else True
            
            if not is_search_page:
                logger.debug("검색 결과 페이지가 아님")
                return []
            
            # NY Post 검색 결과에서 실제 기사 링크들 찾기
            article_links = soup.select('a[href*="/20"]')
            
            found_items = set()  # 중복 제거용
            
            for link in article_links:
                try:
                    url = link.get('href', '')
                    if not url or 'nypost.com' not in url:
                        continue
                    
                    # 기본 제목 가져오기
                    title = link.get_text(strip=True)
                    
                    # 부모 요소에서 더 많은 정보 찾기
                    parent = link.find_parent(['div', 'article'])
                    image_url = ''
                    summary = ''
                    
                    if parent:
                        # .story 클래스 요소 찾기
                        story_container = parent.find_parent(class_=lambda x: x and 'story' in x) or parent
                        
                        if story_container:
                            # 더 나은 제목 찾기
                            title_candidates = [
                                story_container.find('h3'),
                                story_container.find('h2'),
                                story_container.find('h4'),
                                story_container.find(['a', 'span'], string=lambda text: text and len(text.strip()) > 10)
                            ]
                            
                            for candidate in title_candidates:
                                if candidate:
                                    candidate_text = candidate.get_text(strip=True)
                                    if len(candidate_text) > len(title) and len(candidate_text) > 10:
                                        title = candidate_text
                                        break
                            
                            # 요약/설명 찾기
                            summary_selectors = [
                                'p',
                                '.excerpt',
                                '.summary',
                                '[class*="excerpt"]',
                                '[class*="summary"]',
                                '[class*="description"]'
                            ]
                            
                            for selector in summary_selectors:
                                summary_elem = story_container.select_one(selector)
                                if summary_elem:
                                    summary_text = summary_elem.get_text(strip=True)
                                    if len(summary_text) > 20:  # 최소 길이
                                        summary = summary_text
                                        break
                            
                            # 이미지 찾기
                            img_elem = story_container.find('img')
                            if img_elem:
                                image_url = img_elem.get('src', '') or img_elem.get('data-src', '') or img_elem.get('data-lazy-src', '')
                    
                    # 기본 검증
                    if not title or len(title) < 10:
                        continue
                    
                    # 검색어와 관련성 확인 (선택사항)
                    if query and query.lower() not in title.lower() and query.lower() not in summary.lower():
                        # 검색어와 전혀 관련없는 기사는 제외 (너무 엄격하지 않게)
                        pass
                    
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