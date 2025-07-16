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
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
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
                            'image_url': image_url
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
        """기사 페이지에서 추출한 이미지가 유효한 실제 이미지인지 확인"""
        if not url:
            return False
        
        url_lower = url.lower()
        
        # Bangkok Post 로고나 아이콘들 제외
        exclude_patterns = [
            'bp-business.png', 'bp-news.png', 'bp-sports.png', 'bp-tech.png',
            'bangkokpost.png', '/icons/', '/logo', 'favicon',
            'sprite', 'loading', 'placeholder', 'blank.gif',
            'alert.svg', 'icon-close.svg'
        ]
        
        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False
        
        # 데이터 URL 제외
        if url.startswith('data:'):
            return False
        
        # 유효한 이미지 패턴 확인
        valid_patterns = [
            '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp',
            'static.bangkokpost.com',  # Bangkok Post CDN
            '/images/', '/photos/', '/pictures/'
        ]
        
        return any(pattern in url_lower for pattern in valid_patterns)
    
    def _is_valid_bangkokpost_image(self, url: str) -> bool:
        """방콕 포스트 이미지 URL이 유효한지 확인"""
        if not url:
            return False
        
        url_lower = url.lower()
        
        # 제외할 이미지들
        exclude_patterns = [
            'logo', 'alert.svg', 'icon-close.svg', 'favicon',
            'sprite', 'loading', 'placeholder', 'blank.gif'
        ]
        
        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False
        
        # 데이터 URL 제외
        if url.startswith('data:'):
            return False
        
        # 유효한 이미지 확장자나 방콕 포스트 이미지 패턴 확인
        valid_patterns = [
            '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp',
            'bangkokpost.com', 'static.bangkokpost.com'
        ]
        
        return any(pattern in url_lower for pattern in valid_patterns)
    
    def _extract_category_from_url(self, url: str) -> str:
        """URL에서 카테고리 추출"""
        try:
            # Bangkok Post URL 패턴에서 카테고리 추출
            if '/news/' in url:
                return 'news'
            elif '/business/' in url:
                return 'business'
            elif '/sports/' in url:
                return 'sports'
            elif '/tech/' in url or '/technology/' in url:
                return 'technology'
            elif '/world/' in url:
                return 'world'
            elif '/travel/' in url:
                return 'travel'
            elif '/lifestyle/' in url:
                return 'lifestyle'
            elif '/opinion/' in url:
                return 'opinion'
            elif '/auto/' in url:
                return 'auto'
            else:
                return 'news'
        except:
            return 'news'
    
    def get_latest_news(self, category: str = 'news', limit: int = 10) -> List[Dict]:
        """Bangkok Post 최신 뉴스 가져오기"""
        try:
            # 카테고리별 URL 매핑
            category_urls = {
                'news': f"{self.base_url}/thailand",
                'business': f"{self.base_url}/business",
                'sports': f"{self.base_url}/sports", 
                'tech': f"{self.base_url}/tech",
                'world': f"{self.base_url}/world",
                'travel': f"{self.base_url}/travel",
                'lifestyle': f"{self.base_url}/lifestyle",
                'opinion': f"{self.base_url}/opinion",
                'all': self.base_url
            }
            
            url = category_urls.get(category, category_urls['news'])
            
            logger.info(f"Bangkok Post 최신 뉴스 가져오기: {url}")
            
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            articles = self._extract_search_results(response.text, limit)
            logger.info(f"Bangkok Post 최신 뉴스 {len(articles)}개 수집")
            
            # 결과가 없거나 적으면 search_news로 fallback
            if not articles or len(articles) < limit // 2:
                logger.info("Bangkok Post 최신 뉴스 결과 부족, 검색으로 fallback")
                return self.search_news('breaking news', limit)
            
            return articles
            
        except Exception as e:
            logger.error(f"Bangkok Post 최신 뉴스 가져오기 실패: {e}")
            # 404나 다른 오류 시 search_news로 fallback
            logger.info("Bangkok Post 최신 뉴스 실패, 검색으로 fallback")
            try:
                return self.search_news('breaking news', limit)
            except Exception as fallback_error:
                logger.error(f"Bangkok Post fallback 검색도 실패: {fallback_error}")
                return [] 