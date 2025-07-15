# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import logging
from datetime import datetime
import json
import re

logger = logging.getLogger(__name__)

class SCMPScraper:
    """South China Morning Post (SCMP) 뉴스 스크래퍼"""
    
    def __init__(self):
        self.base_url = "https://www.scmp.com"
        self.search_url = "https://www.scmp.com/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
    def search_news(self, query: str, limit: int = 10) -> List[Dict]:
        """SCMP에서 뉴스 검색"""
        try:
            logger.info(f"SCMP 검색: {query}")
            
            # SCMP 검색 요청
            params = {'q': query}
            response = requests.get(self.search_url, params=params, headers=self.headers, timeout=20)
            response.raise_for_status()
            
            # 검색 결과 추출
            articles = self._extract_search_results(response.text, limit, query)
            
            logger.info(f"SCMP에서 {len(articles)}개 검색 결과 찾음")
            return articles
            
        except Exception as e:
            logger.error(f"SCMP 검색 실패: {e}")
            return []
    
    def _extract_search_results(self, html_content: str, limit: int, query: str = '') -> List[Dict]:
        """HTML에서 검색 결과 추출"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # SCMP 검색 결과 패턴 찾기
            selectors = [
                '.search-result',
                '.article-item',
                '.story-item',
                'article',
                '.item',
                '[class*="search"]',
                '[class*="article"]',
                '[class*="story"]',
                'a[href*="/news/"]',
                'a[href*="/business/"]',
                'a[href*="/tech/"]',
                'a[href*="/sport/"]'
            ]
            
            found_items = set()  # 중복 제거용
            
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
                                
                                # 이미지 찾기
                                img_elem = parent.find('img')
                                if img_elem:
                                    image_url = img_elem.get('src', '') or img_elem.get('data-src', '') or img_elem.get('data-lazy-src', '')
                        
                        else:
                            # article, div 등의 컨테이너 요소인 경우
                            # 제목과 링크 찾기
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
                                
                                # 이미지 찾기
                                img_elem = element.find('img')
                                if img_elem:
                                    image_url = img_elem.get('src', '') or img_elem.get('data-src', '') or img_elem.get('data-lazy-src', '')
                        
                        # 기본 검증
                        if not title or not url or len(title) < 10:
                            continue
                        
                        # URL 정규화
                        if url.startswith('/'):
                            url = self.base_url + url
                        elif not url.startswith('http'):
                            continue
                        
                        # SCMP URL인지 확인
                        if 'scmp.com' not in url:
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
                        
                        # 날짜 추출 시도 (URL이나 텍스트에서)
                        published_date = self._extract_date(url, summary)
                        
                        article = {
                            'title': title,
                            'url': url,
                            'summary': summary[:300] if summary else '',
                            'published_date': published_date,
                            'source': 'SCMP',
                            'category': self._extract_category_from_url(url),
                            'scraped_at': datetime.now().isoformat(),
                            'relevance_score': 1,
                            'image_url': image_url
                        }
                        
                        articles.append(article)
                        
                        if len(articles) >= limit:
                            break
                            
                    except Exception as e:
                        logger.debug(f"SCMP 요소 파싱 실패: {e}")
                        continue
                
                if len(articles) >= limit:
                    break
                    
        except Exception as e:
            logger.error(f"SCMP HTML 파싱 실패: {e}")
        
        return articles[:limit]
    
    def _extract_date(self, url: str, text: str) -> str:
        """URL이나 텍스트에서 날짜 추출"""
        try:
            # URL에서 날짜 패턴 찾기 (예: /article/3001234/news-2024/01/15)
            date_patterns = [
                r'/(\d{4})/(\d{1,2})/(\d{1,2})/',  # /2024/01/15/
                r'-(\d{4})-(\d{1,2})-(\d{1,2})',   # -2024-01-15
                r'/article/\d+/.*?(\d{4})/(\d{1,2})/(\d{1,2})'  # SCMP 패턴
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, url)
                if match:
                    groups = match.groups()
                    if len(groups) >= 3:
                        year, month, day = groups[:3]
                        date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
            
            # 텍스트에서 날짜 패턴 찾기
            text_date_patterns = [
                r'(\w+\s+\d{1,2},\s+\d{4})',  # January 15, 2024
                r'(\d{1,2}/\d{1,2}/\d{4})',   # 1/15/2024
                r'(\d{4}-\d{2}-\d{2})',       # 2024-01-15
                r'(\d{1,2}\s+\w+\s+\d{4})',   # 15 January 2024
                r'Published:\s*(\d{1,2}:\d{2}.*?\d{4})',  # Published: time date
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
            '/sport/': 'sport',
            '/news/': 'news',
            '/business/': 'business',
            '/tech/': 'technology',
            '/lifestyle/': 'lifestyle',
            '/culture/': 'culture',
            '/opinion/': 'opinion',
            '/china/': 'china',
            '/asia/': 'asia',
            '/world/': 'world'
        }
        
        for path, category in categories.items():
            if path in url:
                return category
        
        return 'news'
    
    def get_latest_news(self, category: str = 'news', limit: int = 10) -> List[Dict]:
        """카테고리별 최신 뉴스"""
        # 카테고리에 맞는 키워드로 검색
        category_keywords = {
            'news': 'breaking news',
            'sport': 'sports',
            'business': 'business',
            'technology': 'tech',
            'health': 'health',
            'entertainment': 'culture',
            'world': 'asia china'
        }
        
        keyword = category_keywords.get(category, 'news')
        return self.search_news(keyword, limit) 