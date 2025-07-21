# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import logging
from datetime import datetime
import json
import re
import time

logger = logging.getLogger(__name__)

class VNExpressScraper:
    """VN Express 뉴스 스크래퍼 (vnexpress.net - 베트남어 사이트)"""
    
    def __init__(self):
        self.base_url = "https://vnexpress.net"  # 베트남어 메인 사이트 사용
        self.search_url = "https://vnexpress.net/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',  # 베트남어 우선
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
    def search_news(self, query: str, limit: int = 10) -> List[Dict]:
        """VN Express에서 뉴스 검색"""
        try:
            logger.info(f"VN Express 검색: {query}")
            
            # VN Express 검색 URL 패턴
            search_urls = [
                f"https://vnexpress.net/search?q={query}",
                f"https://vnexpress.net/category/news?search={query}",
                f"https://vnexpress.net/?s={query}"
            ]
            
            for search_url in search_urls:
                try:
                    logger.info(f"VN Express 검색 시도: {search_url}")
                    response = requests.get(search_url, headers=self.headers, timeout=15)
                    response.raise_for_status()
                    
                    articles = self._extract_search_results(response.text, limit, query)
                    if articles:
                        logger.info(f"VN Express에서 {len(articles)}개 기사 발견")
                        return articles
                    else:
                        logger.debug(f"검색 결과 없음: {search_url}")
                        
                except Exception as e:
                    logger.debug(f"VN Express 검색 URL 실패 {search_url}: {e}")
                    continue
            
            # 검색 실패 시 최신 뉴스로 대체
            logger.info("VN Express 검색 실패, 최신 뉴스로 대체")
            return self.get_latest_news('news', limit)
            
        except Exception as e:
            logger.error(f"VN Express 검색 실패: {e}")
            return []
    
    def _extract_search_results(self, html_content: str, limit: int, query: str = '') -> List[Dict]:
        """HTML에서 검색 결과 추출"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # VN Express 기사 구조 찾기
            # 일반적인 뉴스 사이트 패턴들을 시도
            article_selectors = [
                'article',
                '.article',
                '.news-item',
                '.story',
                '.post',
                '[class*="article"]',
                '[class*="news"]',
                '[class*="story"]'
            ]
            
            found_items = set()
            
            for selector in article_selectors:
                elements = soup.select(selector)
                if not elements:
                    continue
                    
                logger.debug(f"VN Express {selector}: {len(elements)}개 요소 발견")
                
                for element in elements:
                    try:
                        # 제목 찾기
                        title = ''
                        title_selectors = ['h1', 'h2', 'h3', 'h4', '.title', '.headline', 'a']
                        
                        for title_sel in title_selectors:
                            title_elem = element.find(title_sel)
                            if title_elem:
                                title = title_elem.get_text(strip=True)
                                if len(title) > 15:  # 최소 제목 길이
                                    break
                        
                        if not title or len(title) < 15:
                            continue
                        
                        # URL 찾기
                        url = ''
                        link_elem = element.find('a', href=True)
                        if link_elem:
                            url = link_elem.get('href')
                            
                        # URL 정규화
                        if url and not url.startswith('http'):
                            if url.startswith('/'):
                                url = self.base_url + url
                            else:
                                url = self.base_url + '/' + url
                        
                        if not url or 'vnexpress.net' not in url:
                            continue
                        
                        # 중복 확인
                        if url in found_items:
                            continue
                        found_items.add(url)
                        
                        # 요약 찾기
                        summary = ''
                        summary_selectors = ['p', '.excerpt', '.summary', '.description', '.lead']
                        
                        for sum_sel in summary_selectors:
                            sum_elem = element.find(sum_sel)
                            if sum_elem:
                                sum_text = sum_elem.get_text(strip=True)
                                if len(sum_text) > 30:  # 최소 요약 길이
                                    summary = sum_text
                                    break
                        
                        # 이미지 찾기
                        image_url = ''
                        img_elem = element.find('img')
                        if img_elem:
                            image_url = img_elem.get('src', '') or img_elem.get('data-src', '') or img_elem.get('data-lazy-src', '')
                            
                            # 이미지 URL 정규화
                            if image_url and not image_url.startswith('http'):
                                if image_url.startswith('//'):
                                    image_url = 'https:' + image_url
                                elif image_url.startswith('/'):
                                    image_url = self.base_url + image_url
                        
                        # 날짜 추출
                        published_date = self._extract_date(element, url)
                        
                        # 카테고리 추출
                        category = self._extract_category_from_url(url)
                        
                        article = {
                            'title': title,
                            'url': url,
                            'summary': summary[:300] if summary else title[:200],
                            'published_date': published_date,
                            'source': 'VN Express',
                            'category': category,
                            'scraped_at': datetime.now().isoformat(),
                            'relevance_score': 1,
                            'image_url': image_url
                        }
                        
                        articles.append(article)
                        
                        if len(articles) >= limit:
                            break
                            
                    except Exception as e:
                        logger.debug(f"VN Express 기사 파싱 실패: {e}")
                        continue
                
                if len(articles) >= limit:
                    break
                    
        except Exception as e:
            logger.error(f"VN Express HTML 파싱 실패: {e}")
        
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
                r'\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        date_str = match.group(0)
                        # 날짜 파싱 시도
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
            logger.debug(f"VN Express 날짜 추출 실패: {e}")
        
        # 기본값: 현재 시간
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    def _extract_category_from_url(self, url: str) -> str:
        """URL에서 카테고리 추출"""
        try:
            # VN Express URL 패턴에서 카테고리 추출
            if '/thoi-su' in url:
                return 'news'
            elif '/kinh-doanh' in url:
                return 'business'
            elif '/the-thao' in url:
                return 'sports'
            elif '/khoa-hoc-cong-nghe' in url:
                return 'technology'
            elif '/the-gioi' in url:
                return 'world'
            elif '/du-lich' in url:
                return 'travel'
            elif '/doi-song' in url:
                return 'lifestyle'
            elif '/suc-khoe' in url:
                return 'health'
            else:
                return 'news'
        except:
            return 'news'
    
    def get_latest_news(self, category: str = 'news', limit: int = 10) -> List[Dict]:
        """VN Express 최신 뉴스 가져오기"""
        try:
            # 카테고리별 URL 매핑 (실제 VN Express 베트남어 사이트 구조)
            category_urls = {
                'all': self.base_url,  # 메인 홈페이지
                'news': f"{self.base_url}/thoi-su",  # 시사
                'business': f"{self.base_url}/kinh-doanh",  # 경제/비즈니스
                'sports': f"{self.base_url}/the-thao",  # 스포츠 (사용자 제공)
                'sport': f"{self.base_url}/the-thao", 
                'tech': f"{self.base_url}/khoa-hoc-cong-nghe",  # 과학기술 (사용자 제공)
                'technology': f"{self.base_url}/khoa-hoc-cong-nghe",
                'world': f"{self.base_url}/the-gioi",  # 세계
                'travel': f"{self.base_url}/du-lich",  # 여행
                'health': f"{self.base_url}/suc-khoe",  # 건강 (사용자 제공)
                'life': f"{self.base_url}/doi-song",  # 생활
                'lifestyle': f"{self.base_url}/doi-song",
                'entertainment': f"{self.base_url}/giai-tri"  # 엔터테인먼트 (사용자 제공)
            }
            
            url = category_urls.get(category, category_urls['news'])
            
            logger.info(f"VN Express 최신 뉴스 가져오기: {url}")
            
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            articles = self._extract_search_results(response.text, limit)
            logger.info(f"VN Express 최신 뉴스 {len(articles)}개 수집")
            
            # 결과가 없거나 적으면 search_news로 fallback
            if not articles or len(articles) < limit // 2:
                logger.info("VN Express 최신 뉴스 결과 부족, 검색으로 fallback")
                # 카테고리별 키워드로 검색 (베트남어 키워드 포함)
                search_keywords = {
                    'sports': 'bóng đá thể thao football soccer Vietnam',
                    'sport': 'bóng đá thể thao football soccer Vietnam', 
                    'business': 'kinh tế kinh doanh economy market Vietnam',
                    'technology': 'công nghệ khoa học tech startup innovation Vietnam',
                    'tech': 'công nghệ khoa học tech startup innovation Vietnam',
                    'world': 'thế giới quốc tế international global news',
                    'health': 'sức khỏe y tế health medical Vietnam',
                    'life': 'đời sống lifestyle culture Vietnam',
                    'lifestyle': 'đời sống lifestyle culture Vietnam',
                    'entertainment': 'giải trí entertainment celebrity Vietnam',
                    'news': 'Vietnam tin tức breaking news'
                }
                keyword = search_keywords.get(category, 'breaking news')
                return self.search_news(keyword, limit)
            
            return articles
            
        except Exception as e:
            logger.error(f"VN Express 최신 뉴스 가져오기 실패: {e}")
            # 404나 다른 오류 시 search_news로 fallback
            logger.info("VN Express 최신 뉴스 실패, 검색으로 fallback")
            try:
                # 카테고리별 키워드로 검색 (베트남어 키워드 포함)
                search_keywords = {
                    'sports': 'bóng đá thể thao football soccer Vietnam',
                    'sport': 'bóng đá thể thao football soccer Vietnam', 
                    'business': 'kinh tế kinh doanh economy market Vietnam',
                    'technology': 'công nghệ khoa học tech startup innovation Vietnam',
                    'tech': 'công nghệ khoa học tech startup innovation Vietnam',
                    'world': 'thế giới quốc tế international global news',
                    'health': 'sức khỏe y tế health medical Vietnam',
                    'life': 'đời sống lifestyle culture Vietnam',
                    'lifestyle': 'đời sống lifestyle culture Vietnam',
                    'entertainment': 'giải trí entertainment celebrity Vietnam',
                    'news': 'Vietnam tin tức breaking news'
                }
                keyword = search_keywords.get(category, 'breaking news')
                return self.search_news(keyword, limit)
            except Exception as fallback_error:
                logger.error(f"VN Express fallback 검색도 실패: {fallback_error}")
                return [] 