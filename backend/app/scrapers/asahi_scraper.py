# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import logging
from datetime import datetime, timedelta
import json
import re
import time
from urllib.parse import quote # Added for quote function

logger = logging.getLogger(__name__)

class AsahiScraper:
    """Asahi Shimbun 뉴스 스크래퍼 (www.asahi.com)"""
    
    def __init__(self):
        self.base_url = "https://www.asahi.com"
        self.english_url = "https://www.asahi.com/ajw"  # Asahi Japan Watch (English)
        self.search_url = "https://www.asahi.com/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
    def search_news(self, query: str, limit: int = 10) -> List[Dict]:
        """Asahi Shimbun에서 뉴스 검색"""
        try:
            logger.info(f"Asahi Shimbun 검색: {query}")
            
            # 1단계: 실제 Asahi 검색 API 사용
            articles = self._search_with_api(query, limit)
            if articles:
                logger.info(f"Asahi API에서 {len(articles)}개 기사 발견")
                return articles
            
            # 2단계: 실제로 작동하는 Asahi 검색 URL 사용
            search_urls = [
                f"https://www.asahi.com/ajw/?s={query}",  # 200 status 확인됨
                f"https://www.asahi.com/ajw/search?query={query}",
                f"https://www.asahi.com/?s={query}"
            ]
            
            for search_url in search_urls:
                try:
                    logger.info(f"Asahi 검색 시도: {search_url}")
                    response = requests.get(search_url, headers=self.headers, timeout=15)
                    response.raise_for_status()
                    
                    articles = self._extract_search_results(response.text, limit, query)
                    if articles:
                        logger.info(f"Asahi에서 {len(articles)}개 기사 발견")
                        return articles
                    else:
                        logger.debug(f"검색 결과 없음: {search_url}")
                        
                except Exception as e:
                    logger.debug(f"Asahi 검색 URL 실패 {search_url}: {e}")
                    continue
            
            # 검색 실패 시 영어 섹션 최신 뉴스로 대체
            logger.info("Asahi 검색 실패, 최신 뉴스로 대체")
            return self.get_latest_news('news', limit)
            
        except Exception as e:
            logger.error(f"Asahi 검색 실패: {e}")
            return []
    
    def _search_with_api(self, query: str, limit: int) -> List[Dict]:
        """Asahi 검색 API 사용"""
        try:
            api_url = f"https://sitesearch.asahi.com/sitesearch-api/?Keywords={quote(query)}&start=0&sort=2"
            
            response = requests.get(api_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if 'goo' not in data or 'docs' not in data['goo']:
                logger.debug("Asahi API: 올바른 응답 구조가 아님")
                return []
            
            articles = []
            docs = data['goo']['docs']
            
            for doc in docs[:limit]:
                try:
                    title = doc.get('TITLE', '').strip()
                    body = doc.get('BODY', '').strip()
                    url = doc.get('URL', '').strip()
                    photo_url = doc.get('PHOTOURL', '').strip()  # 이미지 URL 추출
                    
                    if not title or not url or len(title) < 10:
                        continue
                    
                    # URL 정규화
                    if not url.startswith('http'):
                        if url.startswith('/'):
                            url = self.base_url + url
                        else:
                            url = self.base_url + '/' + url
                    
                    # 이미지 URL 정규화
                    image_url = ''
                    if photo_url:
                        if photo_url.startswith('//'):
                            image_url = 'https:' + photo_url
                        elif photo_url.startswith('/'):
                            image_url = self.base_url + photo_url
                        elif photo_url.startswith('http'):
                            image_url = photo_url
                        else:
                            image_url = self.base_url + '/' + photo_url
                    
                    # 날짜 추출 시도 (기본값 사용)
                    published_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
                    
                    article = {
                        'title': title,
                        'url': url,
                        'summary': body[:300] if body else title[:200],
                        'published_date': published_date,
                        'source': 'Asahi Shimbun',
                        'category': self._extract_category_from_url(url),
                        'scraped_at': datetime.now().isoformat(),
                        'relevance_score': 1,
                        'image_url': image_url  # 실제 이미지 URL 사용
                    }
                    
                    articles.append(article)
                    
                except Exception as e:
                    logger.debug(f"Asahi API 문서 파싱 실패: {e}")
                    continue
            
            logger.info(f"Asahi API에서 {len(articles)}개 기사 추출")
            return articles
            
        except Exception as e:
            logger.debug(f"Asahi API 검색 실패: {e}")
            return []
    
    def _extract_search_results(self, html_content: str, limit: int, query: str = '') -> List[Dict]:
        """HTML에서 검색 결과 추출"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Asahi 기사 구조 찾기
            article_selectors = [
                'article',
                '.article',
                '.news-item',
                '.story',
                '.post',
                '.ArticleList_article',
                '.list-article',
                '[class*="article"]',
                '[class*="news"]',
                '[class*="story"]',
                '[class*="list"]'
            ]
            
            found_items = set()
            
            for selector in article_selectors:
                elements = soup.select(selector)
                if not elements:
                    continue
                    
                logger.debug(f"Asahi {selector}: {len(elements)}개 요소 발견")
                
                for element in elements:
                    try:
                        # 제목 찾기
                        title = ''
                        title_selectors = ['h1', 'h2', 'h3', 'h4', '.title', '.headline', '.ArticleList_headline', 'a']
                        
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
                        
                        if not url or 'asahi.com' not in url:
                            continue
                        
                        # 중복 확인
                        if url in found_items:
                            continue
                        found_items.add(url)
                        
                        # 요약 찾기
                        summary = ''
                        summary_selectors = ['p', '.excerpt', '.summary', '.description', '.lead', '.intro', '.ArticleList_summary']
                        
                        for sum_sel in summary_selectors:
                            sum_elem = element.find(sum_sel)
                            if sum_elem:
                                sum_text = sum_elem.get_text(strip=True)
                                if len(sum_text) > 30 and not sum_text.startswith('Asahi'):  # 최소 요약 길이
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
                            'source': 'Asahi Shimbun',
                            'category': category,
                            'scraped_at': datetime.now().isoformat(),
                            'relevance_score': 1,
                            'image_url': image_url
                        }
                        
                        articles.append(article)
                        
                        if len(articles) >= limit:
                            break
                            
                    except Exception as e:
                        logger.debug(f"Asahi 기사 파싱 실패: {e}")
                        continue
                
                if len(articles) >= limit:
                    break
                    
        except Exception as e:
            logger.error(f"Asahi HTML 파싱 실패: {e}")
        
        return articles[:limit]
    
    def _extract_date(self, element, url: str) -> str:
        """요소나 URL에서 날짜 추출"""
        try:
            # 요소에서 날짜 패턴 찾기
            text = element.get_text()
            
            # 다양한 날짜 패턴 (일본 날짜 형식 포함)
            date_patterns = [
                r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
                r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
                r'\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}',
                r'(\d{4}\.\d{1,2}\.\d{1,2})',  # 일본 날짜 형식
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
                        for fmt in ['%m/%d/%Y', '%m-%d-%Y', '%Y/%m/%d', '%Y-%m-%d', '%Y.%m.%d', '%B %d, %Y', '%d %b %Y']:
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
            logger.debug(f"Asahi 날짜 추출 실패: {e}")
        
        # 기본값: 현재 시간
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    def _extract_category_from_url(self, url: str) -> str:
        """URL에서 카테고리 추출"""
        try:
            # Asahi URL 패턴에서 카테고리 추출
            if '/news/' in url or '/national/' in url:
                return 'news'
            elif '/business/' in url or '/economy/' in url:
                return 'business'
            elif '/sports/' in url:
                return 'sports'
            elif '/tech/' in url or '/technology/' in url or '/digital/' in url:
                return 'technology'
            elif '/world/' in url or '/international/' in url:
                return 'world'
            elif '/travel/' in url:
                return 'travel'
            elif '/lifestyle/' in url or '/culture/' in url:
                return 'lifestyle'
            elif '/opinion/' in url or '/editorial/' in url:
                return 'opinion'
            elif '/ajw/' in url:  # Asahi Japan Watch (English section)
                return 'japan'
            else:
                return 'news'
        except:
            return 'news'
    
    def get_latest_news(self, category: str = 'news', limit: int = 10) -> List[Dict]:
        """Asahi Shimbun 최신 뉴스 가져오기"""
        try:
            # 카테고리별 URL 매핑 (영어 섹션 우선)
            category_urls = {
                'news': f"{self.english_url}/national",
                'business': f"{self.english_url}/business",
                'sports': f"{self.english_url}/sports", 
                'tech': f"{self.english_url}/sci-tech",
                'world': f"{self.english_url}/asia-world",
                'japan': f"{self.english_url}",
                'lifestyle': f"{self.english_url}/culture",
                'opinion': f"{self.english_url}/opinion",
                'all': self.english_url
            }
            
            url = category_urls.get(category, category_urls['news'])
            
            logger.info(f"Asahi 최신 뉴스 가져오기: {url}")
            
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            articles = self._extract_search_results(response.text, limit)
            logger.info(f"Asahi 최신 뉴스 {len(articles)}개 수집")
            
            return articles
            
        except Exception as e:
            logger.error(f"Asahi 최신 뉴스 가져오기 실패: {e}")
            return [] 