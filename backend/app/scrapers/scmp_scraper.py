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
            
            # 검색 결과보다 홈페이지를 우선 사용 (이미지가 더 잘 추출됨)
            logger.info("SCMP 홈페이지 직접 사용하여 이미지 포함 기사 추출")
            response = requests.get(self.base_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            homepage_articles = self._extract_articles_from_homepage(response.text, limit)
            
            if homepage_articles:
                logger.info("SCMP 홈페이지에서 {}개 기사 추출 (이미지 포함)".format(len(homepage_articles)))
                return homepage_articles
            elif articles:
                logger.info("SCMP 홈페이지 실패, 검색 결과 {}개 사용".format(len(articles)))
                return articles
            else:
                logger.warning("SCMP 모든 방법 실패")
                return []
            
        except Exception as e:
            logger.error(f"SCMP 접근 실패: {e}")
            return []
    
    def _extract_articles_from_homepage(self, html_content: str, limit: int, requested_category: str = 'all') -> List[Dict]:
        """SCMP 홈페이지에서 기사 추출"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # SCMP 홈페이지의 기사 링크들 찾기
            article_links = []
            
            # 먼저 이미지가 있는 링크들을 우선적으로 찾기
            image_links = []
            for img_elem in soup.find_all('img'):
                parent_link = img_elem.find_parent('a')
                if parent_link:
                    href = parent_link.get('href', '')
                    if '/news/' in href or '/article/' in href:
                        image_links.append(parent_link)
            
            logger.info("SCMP 이미지가 있는 링크: {}개".format(len(image_links)))
            article_links.extend(image_links)
            
            # 추가로 일반 링크들도 찾기
            general_selectors = [
                'h3 a[href*="/news/"]',
                'h2 a[href*="/article/"]',
                'h1 a[href*="/news/"]',
                'a[href*="/article/"]',
                '.headline a',
                '.entry-title a'
            ]
            
            for selector in general_selectors:
                links = soup.select(selector)
                article_links.extend(links)
                if len(article_links) >= limit * 3:
                    break
            
            found_urls = set()
            
            for link in article_links:
                try:
                    href = link.get('href', '')
                    title = link.get_text(strip=True)
                    
                    # 제목 추출 로직 개선 - 빈 제목이나 JSON 스키마 처리
                    original_title = title
                    title_found = False
                    
                    # 방법 1: 기존 제목이 유효한지 확인
                    if title and len(title) > 10 and len(title) < 200 and not title.startswith('{') and '"@context"' not in title:
                        title_found = True
                    
                    # 방법 2: 제목이 없거나 유효하지 않으면 부모 요소에서 찾기
                    if not title_found:
                        parent = link.find_parent()
                        if parent:
                            title_selectors = ['h1', 'h2', 'h3', 'h4', '.title', '.headline', '[class*="title"]']
                            for selector in title_selectors:
                                title_elem = parent.find(selector)
                                if title_elem and title_elem != link:  # 자기 자신은 제외
                                    new_title = title_elem.get_text(strip=True)
                                    if new_title and len(new_title) > 10 and len(new_title) < 200 and not new_title.startswith('{'):
                                        title = new_title
                                        title_found = True
                                        break
                    
                    # 방법 3: 형제 요소에서 찾기
                    if not title_found:
                        for sibling in [link.find_previous_sibling(), link.find_next_sibling()]:
                            if sibling and hasattr(sibling, 'get_text'):
                                sibling_text = sibling.get_text(strip=True)
                                if sibling_text and len(sibling_text) > 10 and len(sibling_text) < 200 and not sibling_text.startswith('{'):
                                    title = sibling_text
                                    title_found = True
                                    break
                    
                    # 방법 4: URL에서 제목 추출 (개선된 방법)
                    if not title_found and href:
                        url_parts = href.split('/')
                        # SCMP URL 구조: /category/subcategory/article/ID/title-slug
                        for part in reversed(url_parts):
                            clean_part = part.split('?')[0]  # 쿼리 파라미터 제거
                            if (len(clean_part) > 15 and '-' in clean_part and 
                                not clean_part.startswith('article') and 
                                not clean_part.isdigit() and  # 숫자 ID 제외
                                not clean_part in ['news', 'economy', 'china', 'world', 'lifestyle', 'sport']):  # 카테고리 제외
                                
                                potential_title = clean_part.replace('-', ' ')
                                # 첫 글자만 대문자로, 나머지는 자연스럽게
                                words = potential_title.split()
                                if len(words) > 3:  # 최소 4단어 이상
                                    formatted_words = []
                                    for i, word in enumerate(words):
                                        if i == 0:  # 첫 번째 단어는 대문자
                                            formatted_words.append(word.capitalize())
                                        elif word.lower() in ['and', 'or', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'as', 'is']:
                                            formatted_words.append(word.lower())
                                        elif word.lower() in ['us', 'uk', 'eu', 'china', 'covid', 'ai']:  # 약어나 고유명사
                                            formatted_words.append(word.upper())
                                        else:
                                            formatted_words.append(word.lower())
                                    
                                    title = ' '.join(formatted_words)
                                    # 첫 글자를 대문자로
                                    title = title[0].upper() + title[1:] if title else title
                                    title_found = True
                                    break
                    
                    # 방법 5: 이미지 alt 텍스트 사용 (마지막 수단으로 사용)
                    if not title_found:
                        img_elem = link.find('img')
                        if img_elem:
                            alt_text = img_elem.get('alt', '')
                            # alt 텍스트가 실제 기사 제목인지 확인 (illustration, photo 등은 제외)
                            if (alt_text and len(alt_text) > 15 and len(alt_text) < 150 and 
                                not alt_text.lower().startswith(('illustration', 'photo', 'image', 'handout')) and
                                not alt_text.startswith('{') and
                                not any(word in alt_text.lower() for word in ['photo:', 'image:', 'getty', 'reuters', 'afp', 'drawing', 'shows'])):
                                title = alt_text[:100] + '...' if len(alt_text) > 100 else alt_text
                                title_found = True
                    
                    # URL 검증 및 정규화
                    if not href:
                        continue
                    
                    # 마지막 수단: 여전히 제목을 찾지 못했다면 기본값 사용 (이미지가 있는 경우만)
                    if not title_found or not title or len(title) < 5:
                        img_elem = link.find('img')
                        if img_elem:
                            # 이미지가 있으면 URL에서 최대한 추출 시도 (더 관대하게)
                            if href:
                                url_parts = href.split('/')
                                for part in reversed(url_parts):
                                    if len(part) > 10 and '-' in part and not part.startswith('article'):
                                        clean_part = part.split('?')[0]
                                        if len(clean_part) > 10:
                                            title = clean_part.replace('-', ' ').title()
                                            title_found = True
                                            break
                            
                            # 정말 마지막 수단
                            if not title_found:
                                title = "SCMP News Article"
                        else:
                            continue
                    
                    # 최종 길이 체크
                    if len(title) < 3:
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
                    
                    # 요약 생성 (제목 기반)
                    summary = title[:100] + "..." if len(title) > 100 else title
                    
                    # 유니코드 문제 해결을 위한 인코딩 처리
                    try:
                        # 제목과 요약에서 문제가 있는 문자 정리
                        title = title.encode('utf-8', 'ignore').decode('utf-8')
                        summary = summary.encode('utf-8', 'ignore').decode('utf-8')
                    except:
                        # 인코딩 실패시 ASCII 안전 버전 사용
                        title = ''.join(c for c in title if ord(c) < 128)
                        summary = ''.join(c for c in summary if ord(c) < 128)
                    
                    # 기본 기사 정보 생성
                    # 카테고리 추출
                    article_category = self._extract_category_from_url(href)
                    
                    # 특정 카테고리가 요청된 경우 필터링
                    if (requested_category and requested_category != 'all' and 
                        requested_category != 'news' and article_category != requested_category):
                        # 특별 케이스들
                        skip_article = True
                        if requested_category == 'entertainment' and article_category == 'culture':
                            skip_article = False
                        elif requested_category == 'politics' and article_category == 'news':
                            # politics 요청 시 china/news도 허용 (URL 확인)
                            if '/china/' in href.lower() or 'politics' in href.lower() or 'government' in href.lower():
                                skip_article = False
                        
                        if skip_article:
                            continue
                    
                    # 특별 케이스 카테고리 재할당
                    final_category = article_category
                    if requested_category == 'entertainment' and article_category == 'culture':
                        final_category = 'entertainment'
                    elif requested_category == 'politics' and article_category == 'news':
                        if '/china/' in href.lower() or 'politics' in href.lower() or 'government' in href.lower():
                            final_category = 'politics'
                    
                    article = {
                        'title': title,
                        'url': href,
                        'summary': summary,
                        'published_date': published_date,
                        'source': 'SCMP',
                        'category': final_category,
                        'scraped_at': datetime.now().isoformat(),
                        'relevance_score': 1,
                        'image_url': image_url or self._get_fallback_image(final_category)
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
        """SCMP 이미지가 유효하고 고유한지 확인 (개선됨)"""
        if not url:
            return False
        
        # 데이터 URL과 blob URL 제외
        if url.startswith('data:') or url.startswith('blob:'):
            return False
        
        url_lower = url.lower()
        
        # SCMP CDN은 우선적으로 허용
        scmp_cdns = [
            'cdn.i-scmp.com', 'i-scmp.com', 'img.scmp.com', 
            'static.scmp.com', 'media.scmp.com'
        ]
        if any(cdn in url_lower for cdn in scmp_cdns):
            return True
        
        # 구체적인 제외 패턴 - UI 요소만 제외
        exclude_patterns = [
            'scmp-logo', 'logo-scmp', 'logo.svg', 'logo.png',
            'favicon.ico', 'favicon.png',
            'icon-', 'sprite-', 'ui-', 'btn-',
            'avatar-default', 'placeholder-', 'no-image',
            'loading-', 'spinner-', 'blank.gif'
        ]
        
        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False
        
        # 크기 체크 - 작은 아이콘들 제외
        small_sizes = ['12x12', '16x16', '20x20', '24x24', '32x32']
        if any(size in url_lower for size in small_sizes):
            return False
        
        # 유효한 이미지 패턴 - 더 포괄적으로
        valid_patterns = [
            '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.svg',
            'scmp.com',
            '/image/', '/images/', '/photo/', '/photos/', '/pictures/',
            '/media/', '/uploads/', '/content/', '/assets/',
            '/canvas/', '/graphics/', '/editorial/',
            'img-', 'photo-', 'picture-', 'image-'
        ]
        
        # 최소 길이 확인
        if len(url) > 30:
            return any(pattern in url_lower for pattern in valid_patterns)
        
        return False
    
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
    
    def _get_fallback_image(self, category: str) -> str:
        """카테고리별 기본 이미지 URL 반환"""
        fallback_images = {
            'business': 'https://images.unsplash.com/photo-1560472355-536de3962603?w=400&h=250&fit=crop',
            'sports': 'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=400&h=250&fit=crop',
            'technology': 'https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=400&h=250&fit=crop',
            'entertainment': 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=400&h=250&fit=crop',
            'lifestyle': 'https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=400&h=250&fit=crop',
            'health': 'https://images.unsplash.com/photo-1559757148-5c350d0d3c56?w=400&h=250&fit=crop',
            'politics': 'https://images.unsplash.com/photo-1541872705-1f73c6400ec9?w=400&h=250&fit=crop',
            'world': 'https://images.unsplash.com/photo-1597149959949-eb37e2a0b30b?w=400&h=250&fit=crop',
            'opinion': 'https://images.unsplash.com/photo-1434030216411-0b793f4b4173?w=400&h=250&fit=crop',
            'news': 'https://images.unsplash.com/photo-1495020689067-958852a7765e?w=400&h=250&fit=crop'
        }
        
        return fallback_images.get(category, fallback_images['news'])

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
        """HTML에서 검색 결과 추출 (개선됨 - 이미지 우선)"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            logger.info("SCMP 검색 결과 HTML 크기: {} 문자".format(len(html_content)))
            
            # 먼저 이미지가 있는 링크들을 우선적으로 찾기 (홈페이지와 동일한 로직)
            image_links = []
            for img_elem in soup.find_all('img'):
                parent_link = img_elem.find_parent('a')
                if parent_link:
                    href = parent_link.get('href', '')
                    if '/news/' in href or '/article/' in href or '/business/' in href or '/tech/' in href or '/sport/' in href:
                        image_links.append(parent_link)
            
            logger.info("SCMP 검색 페이지에서 이미지가 있는 링크: {}개".format(len(image_links)))
            
            # 이미지 링크들을 우선 처리
            found_items = set()
            for link in image_links:
                try:
                    article = self._process_search_link(link, found_items, query)
                    if article:
                        articles.append(article)
                        if len(articles) >= limit:
                            break
                except Exception as e:
                    logger.debug("SCMP 이미지 링크 처리 실패: {}".format(e))
                    continue
            
            # 아직 부족하면 일반 검색 결과 패턴도 시도
            if len(articles) < limit:
                logger.info("SCMP 이미지 링크만으로 부족, 일반 선택자 추가 시도")
                
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
                        
                        # JSON 스키마나 잘못된 제목 필터링
                        if title.startswith('{') or '"@context"' in title or '"@type"' in title:
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
                        
                        # 유니코드 문제 해결을 위한 인코딩 처리
                        try:
                            title = title.encode('utf-8', 'ignore').decode('utf-8')
                            summary = summary.encode('utf-8', 'ignore').decode('utf-8')
                        except:
                            title = ''.join(c for c in title if ord(c) < 128)
                            summary = ''.join(c for c in summary if ord(c) < 128)
                        
                        article = {
                            'title': title,
                            'url': url,
                            'summary': summary[:300] if summary else '',
                            'published_date': published_date,
                            'source': 'SCMP',
                            'category': self._extract_category_from_url(url),
                            'scraped_at': datetime.now().isoformat(),
                            'relevance_score': 1,
                            'image_url': image_url or ''
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
    
    def _process_search_link(self, link, found_items, query):
        """검색 결과 링크를 처리하여 기사 객체 생성"""
        try:
            href = link.get('href', '')
            title = link.get_text(strip=True)
            
            # 제목 정리 - JSON 스키마나 잘못된 데이터 제거
            if title and (title.startswith('{') or '"@context"' in title or '"@type"' in title):
                parent = link.find_parent()
                if parent:
                    title_selectors = ['h1', 'h2', 'h3', 'h4', '.title', '.headline', '[class*="title"]']
                    for selector in title_selectors:
                        title_elem = parent.find(selector)
                        if title_elem:
                            new_title = title_elem.get_text(strip=True)
                            if new_title and not new_title.startswith('{') and len(new_title) > 10 and len(new_title) < 200:
                                title = new_title
                                break
            
            # 기본 검증
            if not title or not href or len(title) < 10:
                return None
            
            # JSON 스키마나 잘못된 제목 필터링
            if title.startswith('{') or '"@context"' in title or '"@type"' in title:
                return None
            
            # URL 정규화
            if href.startswith('/'):
                href = self.base_url + href
            elif not href.startswith('http'):
                return None
            
            # SCMP URL인지 확인
            if 'scmp.com' not in href:
                return None
            
            # 중복 체크
            item_key = (title, href)
            if item_key in found_items:
                return None
            found_items.add(item_key)
            
            # 이미지 추출 (개선된 방법 사용)
            image_url = self._extract_scmp_image(link, href)
            
            # 이미지 URL 정규화
            if image_url and not image_url.startswith('http'):
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url
                elif image_url.startswith('/'):
                    image_url = self.base_url + image_url
            
            # 요약 생성
            summary = title[:100] + "..." if len(title) > 100 else title
            
            # 날짜 추출 시도
            published_date = self._extract_date(href, summary)
            if not published_date:
                published_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
            
            # 유니코드 문제 해결을 위한 인코딩 처리
            try:
                title = title.encode('utf-8', 'ignore').decode('utf-8')
                summary = summary.encode('utf-8', 'ignore').decode('utf-8')
            except:
                title = ''.join(c for c in title if ord(c) < 128)
                summary = ''.join(c for c in summary if ord(c) < 128)
            
            return {
                'title': title,
                'url': href,
                'summary': summary,
                'published_date': published_date,
                'source': 'SCMP',
                'category': self._extract_category_from_url(href),
                'scraped_at': datetime.now().isoformat(),
                'relevance_score': 1,
                'image_url': image_url or ''
            }
            
        except Exception as e:
            logger.debug("SCMP 링크 처리 실패: {}".format(e))
            return None
    
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
        """URL에서 카테고리 추출 (표준화됨)"""
        if not url:
            return 'news'
            
        url_lower = url.lower()
        
        # 표준 카테고리 매핑 (우선순위 순서)
        category_patterns = [
            # 비즈니스/경제 (높은 우선순위)
            ('/business/', 'business'),
            ('/economy/', 'business'),
            ('/markets/', 'business'),
            ('/finance/', 'business'),
            ('economy/china-economy', 'business'),
            ('economy/global-economy', 'business'),
            
            # 스포츠 (높은 우선순위)
            ('/sport/', 'sports'),
            ('/sports/', 'sports'),
            
            # 기술
            ('/tech/', 'technology'),
            ('/technology/', 'technology'),
            
            # 엔터테인먼트 (culture도 포함)
            ('/entertainment/', 'entertainment'),
            ('/culture/', 'entertainment'),  # SCMP culture를 entertainment로 통일
            
            # 라이프스타일
            ('/lifestyle/', 'lifestyle'),
            ('/style/', 'lifestyle'),
            
            # 의견
            ('/opinion/', 'opinion'),
            ('/comment/', 'opinion'),
            
            # 정치
            ('/politics/', 'politics'),
            
            # 국제
            ('/world/', 'world'),
            
            # 지역별 뉴스 (낮은 우선순위)
            ('/china/', 'news'),
            ('/asia/', 'news'),
            ('/news/', 'news'),
            ('/article/', 'news'),
        ]
        
        # 우선순위에 따라 매칭
        for pattern, category in category_patterns:
            if pattern in url_lower:
                return category
        
        # 키워드 기반 추가 분류
        if any(word in url_lower for word in ['market', 'financial', 'trade', 'economic', 'company', 'corporate']):
            return 'business'
        elif any(word in url_lower for word in ['football', 'soccer', 'tennis', 'basketball', 'olympic', 'sport']):
            return 'sports'
        elif any(word in url_lower for word in ['gadget', 'smartphone', 'internet', 'digital', 'software', 'tech']):
            return 'technology'
        elif any(word in url_lower for word in ['politic', 'government', 'minister', 'election']):
            return 'politics'
        elif any(word in url_lower for word in ['health', 'medical', 'hospital']):
            return 'health'
        
        return 'news'
    
    def get_latest_news(self, category: str = 'news', limit: int = 10) -> List[Dict]:
        """카테고리별 최신 뉴스 - 카테고리 URL 우선 사용"""
        try:
            logger.info(f"SCMP 카테고리별 뉴스: {category}")
            
            # 카테고리별 URL 매핑 (SCMP 실제 구조)
            category_urls = {
                'all': self.base_url,
                'news': f"{self.base_url}/news",
                'business': f"{self.base_url}/business", 
                'sport': f"{self.base_url}/sport",
                'sports': f"{self.base_url}/sport",
                'technology': f"{self.base_url}/tech",
                'tech': f"{self.base_url}/tech",
                'lifestyle': f"{self.base_url}/lifestyle",
                'culture': f"{self.base_url}/culture",
                'entertainment': f"{self.base_url}/culture",  # Entertainment maps to culture
                'politics': f"{self.base_url}/news/china",  # Politics maps to China news
                'opinion': f"{self.base_url}/opinion",
                'china': f"{self.base_url}/news/china",
                'asia': f"{self.base_url}/news/asia",
                'world': f"{self.base_url}/news/world"
            }
            
            # URL 우선순위 - 카테고리 URL 먼저 시도, 실패하면 홈페이지
            url_priority = [
                self.base_url,  # 홈페이지 (가장 안정적)
            ]
            
            # 요청된 카테고리 URL을 먼저 시도
            if category != 'all':
                category_url = category_urls.get(category)
                if category_url and category_url != self.base_url:
                    url_priority.insert(0, category_url)
            
            for url in url_priority:
                try:
                    logger.info(f"SCMP 시도 중: {url}")
                    response = requests.get(url, headers=self.headers, timeout=15)
                    response.raise_for_status()
                    
                    # 카테고리별 필터링과 함께 기사 추출
                    articles = self._extract_articles_from_homepage(response.text, limit, category)
                    
                    if articles:
                        logger.info(f"SCMP {url}에서 {len(articles)}개 기사 추출 성공")
                        return articles
                    else:
                        logger.debug(f"SCMP {url}에서 기사 추출 실패")
                        
                except Exception as e:
                    logger.debug(f"SCMP {url} 접근 실패: {e}")
                    continue
            
            logger.warning("SCMP 모든 URL 시도 실패")
            return []
            
        except Exception as e:
            logger.error(f"SCMP 카테고리별 뉴스 실패: {e}")
            return [] 