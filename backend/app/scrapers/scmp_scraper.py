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
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
    def search_news(self, query: str, limit: int = 10) -> List[Dict]:
        """SCMP에서 뉴스 검색 (최신 뉴스로 대체)"""
        try:
            logger.info(f"SCMP 검색: {query} (최신 뉴스 방식)")
            
            # 간단하게 최신 뉴스를 가져오는 방식 사용
            response = requests.get(self.base_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            articles = self._extract_articles_from_homepage(response.text, limit)
            if articles:
                logger.info(f"SCMP에서 {len(articles)}개 최신 뉴스 찾음")
                return articles
            else:
                logger.warning("SCMP 홈페이지에서 기사를 찾을 수 없음")
                return []
            
        except Exception as e:
            logger.error(f"SCMP 접근 실패: {e}")
            return []
    
    def _extract_articles_from_homepage(self, html_content: str, limit: int) -> List[Dict]:
        """SCMP 홈페이지에서 기사 추출"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # SCMP 홈페이지의 기사 링크들 찾기
            article_links = []
            
            # SCMP 기사 링크 선택자
            selectors = [
                'h3 a[href*="/news/"]',  # SCMP 뉴스 URL 패턴
                'h2 a[href*="scmp.com"]',
                'a[href*="/article/"][href*="/"]',
                '.headline a',
                '.entry-title a',
                'h4 a[href*="/"]'
            ]
            
            for selector in selectors:
                links = soup.select(selector)
                article_links.extend(links)
                if len(article_links) >= limit * 2:
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
                    
                    if 'scmp.com' not in href:
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
                        'source': 'SCMP',
                        'category': self._extract_category_from_url(href),
                        'scraped_at': datetime.now().isoformat(),
                        'relevance_score': 1,
                        'image_url': image_url
                    }
                    
                    articles.append(article)
                    
                    if len(articles) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug(f"SCMP 홈페이지 링크 파싱 실패: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"SCMP 홈페이지 HTML 파싱 실패: {e}")
        
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