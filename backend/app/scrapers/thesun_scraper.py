# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import logging
from datetime import datetime
import json
import re

logger = logging.getLogger(__name__)

class TheSunScraper:
    """The Sun 뉴스 스크래퍼"""
    
    def __init__(self):
        self.base_url = "https://www.thesun.co.uk"
        self.search_url = "https://www.thesun.co.uk/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
    def search_news(self, query: str, limit: int = 10) -> List[Dict]:
        """The Sun에서 뉴스 검색"""
        try:
            logger.info("The Sun search: {}".format(query))
            
            # The Sun 검색 요청 (URL 패턴: ?s=query)
            params = {'s': query}
            response = requests.get(self.search_url, params=params, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            # 검색 결과 추출
            articles = self._extract_search_results(response.text, limit, query)
            
            logger.info("The Sun found {} search results".format(len(articles)))
            return articles
            
        except Exception as e:
            logger.error("The Sun search failed: {}".format(e))
            return []
    
    def _extract_search_results(self, html_content: str, limit: int, query: str = '') -> List[Dict]:
        """HTML에서 검색 결과 추출"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # The Sun 검색 결과 패턴 찾기
            selectors = [
                '.teaser',
                '.story',
                '.article',
                'article',
                '.post',
                '[class*="teaser"]',
                '[class*="story"]',
                '[class*="article"]',
                'a[href*="/news/"]',
                'a[href*="/sport/"]',
                'a[href*="/money/"]',
                'a[href*="/tech/"]',
                'a[href*="/fabulous/"]',
                'h2, h3, h4'  # 제목 요소들도 포함
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
                            parent = element.find_parent(['article', 'div', 'section'])
                            if parent:
                                # 더 나은 제목 찾기
                                title_elem = parent.find(['h1', 'h2', 'h3', 'h4'])
                                if title_elem and len(title_elem.get_text(strip=True)) > len(title):
                                    title = title_elem.get_text(strip=True)
                                
                                # 요약 찾기
                                summary_elem = parent.find(['p', '.excerpt', '.summary', '.description'])
                                if summary_elem:
                                    summary = summary_elem.get_text(strip=True)
                                
                                # 이미지 찾기 - 개선된 로직
                                image_url = self._extract_image_from_element(parent)
                        
                        elif element.name in ['h2', 'h3', 'h4']:
                            # 헤딩 요소인 경우
                            title = element.get_text(strip=True)
                            
                            # 링크 찾기
                            link_elem = element.find('a')
                            if not link_elem:
                                # 부모나 주변에서 링크 찾기
                                parent = element.find_parent(['div', 'article', 'section'])
                                if parent:
                                    link_elem = parent.find('a')
                            
                            if link_elem:
                                url = link_elem.get('href', '')
                                
                                # 상위 컨테이너에서 요약과 이미지 찾기
                                parent_container = element.find_parent(['div', 'article', 'section'])
                                if parent_container:
                                    # 요약 찾기
                                    summary_elem = parent_container.find(['p', '.excerpt', '.summary', '.description'])
                                    if summary_elem:
                                        summary = summary_elem.get_text(strip=True)
                                    
                                    # 이미지 찾기
                                    image_url = self._extract_image_from_element(parent_container)
                        
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
                                image_url = self._extract_image_from_element(element)
                        
                        # 기본 검증
                        if not title or not url or len(title) < 10:
                            continue
                        
                        # URL 정규화
                        if url.startswith('/'):
                            url = self.base_url + url
                        elif not url.startswith('http'):
                            continue
                        
                        # The Sun URL인지 확인
                        if 'thesun.co.uk' not in url:
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
                            'source': 'The Sun',
                            'category': self._extract_category_from_url(url),
                            'scraped_at': datetime.now().isoformat(),
                            'relevance_score': 1,
                            'image_url': image_url
                        }
                        
                        articles.append(article)
                        
                        if len(articles) >= limit:
                            break
                            
                    except Exception as e:
                        logger.debug("The Sun element parsing failed: {}".format(e))
                        continue
                
                if len(articles) >= limit:
                    break
                    
        except Exception as e:
            logger.error("The Sun HTML parsing failed: {}".format(e))
        
        return articles[:limit]
    
    def _extract_image_from_element(self, element) -> str:
        """요소에서 이미지 URL 추출"""
        image_url = ''
        
        try:
            # 이미지 찾기 - 여러 방법으로 시도
            img_selectors = [
                'img[src*="thesun"]',  # The Sun 특화 이미지
                'picture img',  # picture 태그 안의 이미지
                'img[class*="hero"]',  # 히어로 이미지
                'img[class*="main"]',  # 메인 이미지
                'img[class*="featured"]',  # 피처드 이미지
                'img[data-src]',  # lazy load 이미지
                'img',  # 일반 이미지
            ]
            
            for img_sel in img_selectors:
                img_elem = element.select_one(img_sel)
                if img_elem:
                    # 다양한 속성에서 이미지 URL 시도
                    image_url = (img_elem.get('src', '') or 
                                img_elem.get('data-src', '') or 
                                img_elem.get('data-lazy-src', '') or
                                img_elem.get('data-original', '') or
                                img_elem.get('srcset', '').split(',')[0].split(' ')[0])
                    
                    # 유효한 이미지 URL인지 확인
                    if image_url and any(ext in image_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                        break
                    else:
                        image_url = ''
        
        except Exception as e:
            logger.debug("Image extraction failed: {}".format(e))
        
        return image_url
    
    def _extract_date(self, url: str, text: str) -> str:
        """URL이나 텍스트에서 날짜 추출"""
        try:
            # URL에서 날짜 패턴 찾기 (예: /2024/01/15/)
            date_pattern = r'/(\d{4})/(\d{1,2})/(\d{1,2})/'
            match = re.search(date_pattern, url)
            if match:
                year, month, day = match.groups()
                date_str = "{}-{}-{}".format(year, month.zfill(2), day.zfill(2))
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
            
            # 텍스트에서 날짜 패턴 찾기
            text_date_patterns = [
                r'(\w+\s+\d{1,2},\s+\d{4})',  # January 15, 2024
                r'(\d{1,2}/\d{1,2}/\d{4})',   # 1/15/2024
                r'(\d{4}-\d{2}-\d{2})',       # 2024-01-15
                r'(\d{1,2}\s+\w+\s+\d{4})',   # 15 January 2024
            ]
            
            for pattern in text_date_patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(1)
                    
        except Exception as e:
            logger.debug("Date extraction failed: {}".format(e))
        
        return ''
    
    def _extract_category_from_url(self, url: str) -> str:
        """URL에서 카테고리 추출"""
        categories = {
            '/sport/': 'sport',
            '/news/': 'news',
            '/money/': 'business',
            '/tech/': 'technology',
            '/health/': 'health',
            '/showbiz/': 'entertainment',
            '/motors/': 'motors',
            '/travel/': 'travel',
            '/fabulous/': 'lifestyle'
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
            'sport': 'football',
            'business': 'money',
            'technology': 'tech',
            'health': 'health',
            'entertainment': 'showbiz'
        }
        
        keyword = category_keywords.get(category, 'news')
        return self.search_news(keyword, limit) 