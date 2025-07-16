# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import logging
from datetime import datetime
import json
import re

logger = logging.getLogger(__name__)

class DailyMailScraper:
    """Daily Mail 뉴스 스크래퍼"""
    
    def __init__(self):
        self.base_url = "https://www.dailymail.co.uk"
        self.search_url = "https://www.dailymail.co.uk/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
    def search_news(self, query: str, limit: int = 10) -> List[Dict]:
        """Daily Mail에서 뉴스 검색 (개선된 검색 기능)"""
        try:
            from urllib.parse import quote
            import time
            
            logger.info(f"Daily Mail 검색: {query}")
            
            # 더 나은 헤더 설정
            improved_headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            # 여러 검색 URL 시도
            search_urls = [
                f"https://www.dailymail.co.uk/home/search.html?sel=site&searchPhrase={quote(query)}",
                f"https://www.dailymail.co.uk/search?q={quote(query)}",
                f"https://www.dailymail.co.uk/news/index.html",  # 뉴스 섹션
                self.base_url  # 홈페이지 폴백
            ]
            
            for i, search_url in enumerate(search_urls):
                try:
                    logger.info(f"Daily Mail 시도 {i+1}: {search_url}")
                    
                    # 점진적으로 타임아웃 늘리기
                    timeout = 10 + (i * 5)
                    
                    response = requests.get(
                        search_url, 
                        headers=improved_headers, 
                        timeout=timeout,
                        allow_redirects=True
                    )
                    response.raise_for_status()
                    
                    if i < 2:  # 실제 검색 URL들
                        articles = self._extract_search_results(response.text, limit, query)
                    else:  # 홈페이지나 뉴스 섹션
                        articles = self._extract_articles_from_homepage(response.text, limit)
                    
                    if articles:
                        logger.info(f"Daily Mail 검색 결과: {len(articles)}개 기사 찾음")
                        return articles
                        
                    # 짧은 대기 시간
                    time.sleep(1)
                    
                except requests.exceptions.Timeout:
                    logger.warning(f"Daily Mail 타임아웃: {search_url}")
                    continue
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Daily Mail 요청 실패: {search_url} - {e}")
                    continue
                except Exception as e:
                    logger.debug(f"Daily Mail 파싱 실패: {search_url} - {e}")
                    continue
            
            logger.warning("Daily Mail에서 기사를 찾을 수 없음")
            return []
            
        except Exception as e:
            logger.error(f"Daily Mail 접근 실패: {e}")
            return []
    
    def _extract_articles_from_homepage(self, html_content: str, limit: int) -> List[Dict]:
        """Daily Mail 홈페이지에서 기사 추출"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Daily Mail 홈페이지의 기사 링크들 찾기
            article_links = []
            
            # Daily Mail 기사 링크 선택자
            selectors = [
                'h2 a[href*="/article-"]',  # Daily Mail 기사 URL 패턴
                '.headline a[href*="dailymail.co.uk"]',
                'a[href*="/article-"][href*="/"]',
                '.entry-title a',
                '.linkro-darkred'
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
                    
                    if 'dailymail.co.uk' not in href:
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
                    
                    # Daily Mail 날짜 추출 개선
                    published_date = self._extract_dailymail_date(link, href)
                    
                    # 기본 기사 정보 생성
                    article = {
                        'title': title,
                        'url': href,
                        'summary': '',
                        'published_date': published_date,
                        'source': 'Daily Mail',
                        'category': self._extract_category_from_url(href),
                        'scraped_at': datetime.now().isoformat(),
                        'relevance_score': 1,
                        'image_url': image_url
                    }
                    
                    articles.append(article)
                    
                    if len(articles) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug(f"Daily Mail 홈페이지 링크 파싱 실패: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Daily Mail 홈페이지 HTML 파싱 실패: {e}")
        
        return articles[:limit]
    
    def _extract_dailymail_date(self, link_elem, article_url: str) -> str:
        """Daily Mail 기사에서 날짜 추출 (향상된 버전)"""
        try:
            # 1. 링크 주변 요소에서 날짜 찾기
            parent = link_elem.find_parent()
            if parent:
                # time 요소 찾기
                time_elem = parent.find('time')
                if time_elem:
                    datetime_attr = time_elem.get('datetime')
                    if datetime_attr:
                        try:
                            if 'T' in datetime_attr:
                                date_obj = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                            else:
                                date_obj = datetime.fromisoformat(datetime_attr)
                            return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                        except:
                            pass
                    
                    time_text = time_elem.get_text(strip=True)
                    if time_text:
                        parsed_date = self._parse_dailymail_date_text(time_text)
                        if parsed_date:
                            return parsed_date
                
                # Daily Mail 특정 클래스들
                date_selectors = [
                    '.date', '.time', '.published', '.timestamp', '.article-timestamp',
                    '[class*="date"]', '[class*="time"]', '[class*="publish"]'
                ]
                
                for selector in date_selectors:
                    date_elem = parent.select_one(selector)
                    if date_elem:
                        date_text = date_elem.get_text(strip=True)
                        if date_text:
                            parsed_date = self._parse_dailymail_date_text(date_text)
                            if parsed_date:
                                return parsed_date
            
            # 2. URL에서 날짜 추출 (Daily Mail 특화)
            date_from_url = self._extract_dailymail_date_from_url(article_url)
            if date_from_url:
                return date_from_url
            
            # 3. 실제 기사 페이지에서 날짜 추출
            return self._extract_dailymail_date_from_page(article_url)
            
        except Exception as e:
            logger.debug("Daily Mail 날짜 추출 실패: {}".format(e))
        
        return ''
    
    def _parse_dailymail_date_text(self, text: str) -> str:
        """Daily Mail 날짜 텍스트 파싱"""
        try:
            # Daily Mail 스타일: "Published: 10:30 EST, 15 July 2024"
            if 'Published:' in text:
                # Published 이후 부분 추출
                pub_match = re.search(r'Published:\s*(.+)', text, re.IGNORECASE)
                if pub_match:
                    date_part = pub_match.group(1)
                    # 시간과 날짜 분리
                    date_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4})', date_part)
                    if date_match:
                        return date_match.group(1)
            
            # 상대적 시간 패턴
            relative_patterns = [
                (r'(\d+)\s*hours?\s*ago', 'hours'),
                (r'(\d+)\s*days?\s*ago', 'days'),
                (r'(\d+)\s*minutes?\s*ago', 'minutes'),
                (r'(\d+)\s*weeks?\s*ago', 'weeks')
            ]
            
            for pattern, unit in relative_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    amount = int(match.group(1))
                    from datetime import timedelta
                    
                    if unit == 'hours':
                        date_obj = datetime.now() - timedelta(hours=amount)
                    elif unit == 'days':
                        date_obj = datetime.now() - timedelta(days=amount)
                    elif unit == 'minutes':
                        date_obj = datetime.now() - timedelta(minutes=amount)
                    elif unit == 'weeks':
                        date_obj = datetime.now() - timedelta(weeks=amount)
                    
                    return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
            
            # 절대적 날짜 패턴들
            date_patterns = [
                r'(\d{1,2}\s+\w+\s+\d{4})',   # 15 July 2024
                r'(\w+\s+\d{1,2},?\s+\d{4})', # July 15, 2024
                r'(\d{1,2}/\d{1,2}/\d{4})',   # 15/07/2024
                r'(\d{4}-\d{2}-\d{2})',       # 2024-07-15
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(1)
                    
        except Exception as e:
            logger.debug("Daily Mail 날짜 텍스트 파싱 실패: {}".format(e))
        
        return ''
    
    def _extract_dailymail_date_from_url(self, url: str) -> str:
        """Daily Mail URL에서 날짜 추출"""
        try:
            # Daily Mail URL 패턴: /article-12345678/news-title-2024-07-15.html
            patterns = [
                r'/article-\d+/.*?(\d{4})-(\d{1,2})-(\d{1,2})',  # Daily Mail 기사 패턴
                r'/(\d{4})/(\d{1,2})/(\d{1,2})/',  # /2024/07/15/
                r'-(\d{4})-(\d{1,2})-(\d{1,2})',   # -2024-07-15
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    groups = match.groups()
                    if len(groups) >= 3:
                        year, month, day = groups[:3]
                        try:
                            date_obj = datetime(int(year), int(month), int(day))
                            return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                        except:
                            continue
                            
        except Exception as e:
            logger.debug("Daily Mail URL에서 날짜 추출 실패: {}".format(e))
        
        return ''
    
    def _extract_dailymail_date_from_page(self, article_url: str) -> str:
        """Daily Mail 기사 페이지에서 날짜 추출"""
        try:
            response = requests.get(article_url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 메타 태그에서 날짜 찾기
                meta_selectors = [
                    'meta[property="article:published_time"]',
                    'meta[name="publication_date"]',
                    'meta[name="publishdate"]',
                    'meta[property="article:modified_time"]'
                ]
                
                for selector in meta_selectors:
                    meta_elem = soup.select_one(selector)
                    if meta_elem:
                        content = meta_elem.get('content', '')
                        if content:
                            try:
                                date_obj = datetime.fromisoformat(content.replace('Z', '+00:00'))
                                return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                            except:
                                pass
                
                # Daily Mail 기사 페이지 특정 요소들
                content_selectors = [
                    'time[datetime]',
                    '.article-timestamp',
                    '.published',
                    '[class*="date"]',
                    '[class*="time"]',
                    '.byline-section time'
                ]
                
                for selector in content_selectors:
                    elem = soup.select_one(selector)
                    if elem:
                        datetime_attr = elem.get('datetime', '')
                        if datetime_attr:
                            try:
                                date_obj = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                                return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                            except:
                                pass
                        
                        text = elem.get_text(strip=True)
                        if text:
                            parsed_date = self._parse_dailymail_date_text(text)
                            if parsed_date:
                                return parsed_date
                                
        except Exception as e:
            logger.debug("Daily Mail 기사 페이지에서 날짜 추출 실패: {}".format(e))
        
        # 현재 시간을 기본값으로 (최신 뉴스라고 가정)
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')

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
            
            # Daily Mail 검색 결과 패턴 찾기
            selectors = [
                '.sch-res-item',
                '.article',
                '.story',
                'article',
                '.search-result',
                '[class*="article"]',
                '[class*="story"]',
                '[class*="sch-res"]',
                'a[href*="/article-"]',
                'a[href*="/news/"]',
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
                        
                        # Daily Mail URL인지 확인
                        if 'dailymail.co.uk' not in url:
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
                            'source': 'Daily Mail',
                            'category': self._extract_category_from_url(url),
                            'scraped_at': datetime.now().isoformat(),
                            'relevance_score': 1,
                            'image_url': image_url
                        }
                        
                        articles.append(article)
                        
                        if len(articles) >= limit:
                            break
                            
                    except Exception as e:
                        logger.debug(f"Daily Mail 요소 파싱 실패: {e}")
                        continue
                
                if len(articles) >= limit:
                    break
                    
        except Exception as e:
            logger.error(f"Daily Mail HTML 파싱 실패: {e}")
        
        return articles[:limit]
    
    def _extract_date(self, url: str, text: str) -> str:
        """URL이나 텍스트에서 날짜 추출"""
        try:
            # URL에서 날짜 패턴 찾기 (예: /article-12345678/news-2024-01-15.html)
            date_patterns = [
                r'/(\d{4})/(\d{1,2})/(\d{1,2})/',  # /2024/01/15/
                r'-(\d{4})-(\d{1,2})-(\d{1,2})',   # -2024-01-15
                r'/article-\d+/.*?-(\d{4})-(\d{1,2})-(\d{1,2})'  # Daily Mail 특별 패턴
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, url)
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
                r'(\d{1,2}\s+\w+\s+\d{4})',   # 15 January 2024
                r'Published:\s*(\d{1,2}:\d{2}.*?\d{4})',  # Daily Mail 스타일
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
            '/money/': 'business',
            '/sciencetech/': 'technology',
            '/health/': 'health',
            '/tvshowbiz/': 'entertainment',
            '/travel/': 'travel',
            '/femail/': 'lifestyle',
            '/home/': 'home',
            '/property/': 'property'
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
            'entertainment': 'celebrity'
        }
        
        keyword = category_keywords.get(category, 'news')
        return self.search_news(keyword, limit) 