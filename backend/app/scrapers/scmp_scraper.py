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
        """SCMP에서 뉴스 검색 (개선된 검색 기능)"""
        try:
            from urllib.parse import quote
            
            logger.info(f"SCMP 검색: {query}")
            
            # SCMP 실제 검색 API 사용 - 다양한 URL 패턴 시도
            search_urls = [
                f"https://www.scmp.com/rss/2/feed",  # RSS 피드
                f"https://www.scmp.com/search?q={quote(query)}",  # 수정된 파라미터
                f"https://www.scmp.com/news",  # 뉴스 섹션
                f"https://www.scmp.com/topics/{quote(query)}"  # 토픽 검색
            ]
            
            articles = []
            
            for search_url in search_urls:
                try:
                    logger.info(f"시도 중: {search_url}")
                    response = requests.get(search_url, headers=self.headers, timeout=10)
                    response.raise_for_status()
                    
                    extracted_articles = self._extract_search_results(response.text, limit, query)
                    
                    if extracted_articles:
                        # 쿼리와 관련성이 높은 기사들만 필터링
                        relevant_articles = self._filter_relevant_articles(extracted_articles, query)
                        articles.extend(relevant_articles)
                        
                        if len(articles) >= limit:
                            articles = articles[:limit]
                            break
                            
                except Exception as e:
                    logger.debug(f"검색 URL 시도 실패: {search_url} - {e}")
                    continue
            
            if articles:
                logger.info(f"SCMP 검색 결과: {len(articles)}개 기사 찾음")
                return articles
            else:
                # 검색 결과가 없으면 홈페이지 최신 뉴스로 폴백
                logger.info(f"SCMP 검색 결과 없음, 홈페이지 최신 뉴스로 폴백")
                response = requests.get(self.base_url, headers=self.headers, timeout=10)
                response.raise_for_status()
                articles = self._extract_articles_from_homepage(response.text, limit)
                return articles
            
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
                    
                    # SCMP 이미지 추출 개선
                    image_url = self._extract_scmp_image(link, href)
                    
                    # 이미지 URL 정규화
                    if image_url:
                        if image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        elif image_url.startswith('/'):
                            image_url = self.base_url + image_url
                        elif not image_url.startswith('http'):
                            image_url = self.base_url + '/' + image_url
                    
                    # SCMP 날짜 추출 개선
                    published_date = self._extract_scmp_date(link, href)
                    
                    # 기본 기사 정보 생성
                    article = {
                        'title': title,
                        'url': href,
                        'summary': '',
                        'published_date': published_date,
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
    
    def _filter_relevant_articles(self, articles: List[Dict], query: str) -> List[Dict]:
        """검색어와 관련성이 높은 기사들만 필터링"""
        if not query or not articles:
            return articles
        
        query_words = query.lower().split()
        relevant_articles = []
        
        for article in articles:
            title = article.get('title', '').lower()
            summary = article.get('summary', '').lower()
            
            # 관련성 점수 계산
            relevance_score = 0
            
            for word in query_words:
                # 제목에서 발견되면 높은 점수
                if word in title:
                    relevance_score += 3
                # 요약에서 발견되면 중간 점수
                elif word in summary:
                    relevance_score += 1
            
            # 관련성이 있는 기사만 포함
            if relevance_score > 0:
                article['relevance_score'] = relevance_score
                relevant_articles.append(article)
        
        # 관련성 점수로 정렬
        relevant_articles.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return relevant_articles
    
    def _extract_scmp_image(self, link_elem, article_url: str) -> str:
        """SCMP 기사에서 고유한 이미지 추출"""
        image_url = ''
        
        try:
            # 1. 링크 요소 자체에서 이미지 찾기
            img_elem = link_elem.find('img')
            if img_elem:
                for attr in ['src', 'data-src', 'data-lazy-src', 'data-original', 'data-img']:
                    img_src = img_elem.get(attr, '')
                    if img_src and self._is_valid_scmp_image(img_src):
                        image_url = img_src
                        break
            
            # 2. 링크의 직접 부모에서 이미지 찾기 (더 정확한 연관성)
            if not image_url:
                parent = link_elem.find_parent()
                if parent:
                    # 부모 컨테이너 내 모든 이미지 찾기
                    img_elems = parent.find_all('img')
                    for img_elem in img_elems:
                        for attr in ['src', 'data-src', 'data-lazy-src', 'data-original']:
                            img_src = img_elem.get(attr, '')
                            if img_src and self._is_valid_scmp_image(img_src):
                                image_url = img_src
                                break
                        if image_url:
                            break
            
            # 3. 형제 요소에서 이미지 찾기 (특히 이전 형제)
            if not image_url:
                prev_sibling = link_elem.find_previous_sibling()
                next_sibling = link_elem.find_next_sibling()
                
                for sibling in [prev_sibling, next_sibling]:
                    if sibling and hasattr(sibling, 'find'):
                        img_elem = sibling.find('img')
                        if img_elem:
                            for attr in ['src', 'data-src', 'data-lazy-src']:
                                img_src = img_elem.get(attr, '')
                                if img_src and self._is_valid_scmp_image(img_src):
                                    image_url = img_src
                                    break
                        if image_url:
                            break
            
            # 4. 실제 기사 페이지에서 이미지 추출 (마지막 수단)
            if not image_url:
                image_url = self._extract_image_from_article_page(article_url)
                
        except Exception as e:
            logger.debug("SCMP 이미지 추출 실패: {}".format(e))
        
        return image_url
    
    def _is_valid_scmp_image(self, url: str) -> bool:
        """SCMP 이미지가 유효하고 고유한지 확인"""
        if not url:
            return False
        
        # 특정 공통 이미지만 제외 (너무 엄격하지 않게)
        exclude_patterns = [
            'canvas/2025/07/15/15188ae4',  # 발견된 특정 공통 이미지 ID
            'placeholder.', 'logo.', 'default.', 'avatar.',
            'sprite.', 'icon.', 'loading.', 'blank.',
            'spacer.', 'transparent.'
        ]
        
        url_lower = url.lower()
        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False
        
        # 데이터 URL 제외
        if url.startswith('data:'):
            return False
        
        # 유효한 이미지 패턴 확인 (SCMP CDN 포함)
        valid_patterns = [
            '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp',
            'image', 'photo', 'picture', 'img',
            'cdn.i-scmp.com',                  # SCMP CDN 허용
                '/images/', '/photos/', '/pictures/',
                'i-scmp.com'  # SCMP 이미지 CDN
        ]
        
        return any(pattern in url_lower for pattern in valid_patterns)
    
    def _extract_image_from_article_page(self, article_url: str) -> str:
        """실제 기사 페이지에서 메인 이미지 추출"""
        try:
            response = requests.get(article_url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # SCMP 기사 페이지의 메인 이미지 찾기
                selectors = [
                    'meta[property="og:image"]',
                    'meta[name="twitter:image"]',
                    '.hero-image img',
                    '.article-image img',
                    '.story-image img',
                    'figure img',
                    '.main-image img'
                ]
                
                for selector in selectors:
                    elem = soup.select_one(selector)
                    if elem:
                        img_url = elem.get('content') or elem.get('src') or elem.get('data-src')
                        if img_url and self._is_valid_scmp_image(img_url):
                            return img_url
                            
        except Exception as e:
            logger.debug("기사 페이지에서 이미지 추출 실패: {}".format(e))
        
        return ''
    
    def _extract_scmp_date(self, link_elem, article_url: str) -> str:
        """SCMP 기사에서 날짜 추출 (향상된 버전)"""
        try:
            # 1. 링크 주변 요소에서 날짜 찾기
            parent = link_elem.find_parent()
            if parent:
                # 시간/날짜 관련 요소들 찾기
                time_elem = parent.find('time')
                if time_elem:
                    datetime_attr = time_elem.get('datetime')
                    if datetime_attr:
                        # ISO 형식 날짜 처리
                        try:
                            if 'T' in datetime_attr:
                                date_obj = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                            else:
                                date_obj = datetime.fromisoformat(datetime_attr)
                            return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                        except:
                            pass
                    
                    # time 요소의 텍스트에서 날짜 추출
                    time_text = time_elem.get_text(strip=True)
                    if time_text:
                        date_result = self._parse_date_text(time_text)
                        if date_result:
                            return date_result
                
                # 날짜 클래스를 가진 요소들 찾기
                date_selectors = [
                    '.date', '.time', '.published', '.timestamp',
                    '[class*="date"]', '[class*="time"]', '[class*="publish"]'
                ]
                
                for selector in date_selectors:
                    date_elem = parent.select_one(selector)
                    if date_elem:
                        date_text = date_elem.get_text(strip=True)
                        if date_text:
                            date_result = self._parse_date_text(date_text)
                            if date_result:
                                return date_result
            
            # 2. URL에서 날짜 패턴 찾기 (SCMP 특화)
            date_from_url = self._extract_date_from_url(article_url)
            if date_from_url:
                return date_from_url
            
            # 3. 실제 기사 페이지에서 날짜 추출
            return self._extract_date_from_article_page(article_url)
            
        except Exception as e:
            logger.debug("SCMP 날짜 추출 실패: {}".format(e))
        
        return ''
    
    def _parse_date_text(self, text: str) -> str:
        """텍스트에서 날짜 파싱"""
        try:
            # 상대적 시간 패턴 (1시간 전, 2일 전 등)
            relative_patterns = [
                (r'(\d+)\s*hours?\s*ago', 'hours'),
                (r'(\d+)\s*days?\s*ago', 'days'),
                (r'(\d+)\s*minutes?\s*ago', 'minutes'),
                (r'(\d+)\s*weeks?\s*ago', 'weeks'),
                (r'(\d+)\s*months?\s*ago', 'months')
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
                    elif unit == 'months':
                        date_obj = datetime.now() - timedelta(days=amount*30)
                    
                    return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
            
            # 절대적 날짜 패턴들
            date_patterns = [
                r'(\w+\s+\d{1,2},?\s+\d{4})',  # January 15, 2024
                r'(\d{1,2}\s+\w+\s+\d{4})',   # 15 January 2024
                r'(\d{1,2}/\d{1,2}/\d{4})',   # 1/15/2024
                r'(\d{4}-\d{2}-\d{2})',       # 2024-01-15
                r'(\d{1,2}\.\d{1,2}\.\d{4})', # 15.1.2024
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(1)
                    
        except Exception as e:
            logger.debug("날짜 텍스트 파싱 실패: {}".format(e))
        
        return ''
    
    def _extract_date_from_url(self, url: str) -> str:
        """URL에서 날짜 추출 (SCMP 특화)"""
        try:
            # SCMP URL 패턴: /article/3318319/...
            # 숫자 ID에서 날짜 정보 추출 가능성 확인
            
            # 일반적인 URL 날짜 패턴들
            patterns = [
                r'/(\d{4})/(\d{1,2})/(\d{1,2})/',  # /2024/07/15/
                r'-(\d{4})-(\d{1,2})-(\d{1,2})',   # -2024-07-15
                r'/article/\d+/.*?(\d{4})/(\d{1,2})/(\d{1,2})'  # SCMP 기사 패턴
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
            logger.debug("URL에서 날짜 추출 실패: {}".format(e))
        
        return ''
    
    def _extract_date_from_article_page(self, article_url: str) -> str:
        """실제 기사 페이지에서 날짜 추출"""
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
                
                # 기사 본문에서 날짜 찾기
                content_selectors = [
                    'time[datetime]',
                    '.date', '.published', '.timestamp',
                    '[class*="date"]', '[class*="time"]'
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
                            parsed_date = self._parse_date_text(text)
                            if parsed_date:
                                return parsed_date
                                
        except Exception as e:
            logger.debug("기사 페이지에서 날짜 추출 실패: {}".format(e))
        
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