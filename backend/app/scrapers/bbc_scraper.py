import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import logging
from datetime import datetime
import json
import re

logger = logging.getLogger(__name__)

class BBCNewsScraper:
    """BBC 뉴스 스크래퍼 (실제 검색 페이지 활용)"""
    
    def __init__(self):
        self.base_url = "https://www.bbc.com"
        self.search_url = "https://www.bbc.com/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
    def search_news(self, query: str, limit: int = 10) -> List[Dict]:
        """실제 BBC 검색 페이지에서 검색 결과 가져오기"""
        try:
            logger.info(f"BBC 실제 검색: {query}")
            
            # BBC 검색 요청
            params = {'q': query}
            response = requests.get(self.search_url, params=params, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            # JSON 데이터 추출
            articles = self._extract_search_results(response.text, limit)
            
            logger.info(f"BBC에서 {len(articles)}개 실제 검색 결과 찾음")
            return articles
            
        except Exception as e:
            logger.error(f"BBC 실제 검색 실패: {e}")
            return []
    
    def _extract_search_results(self, html_content: str, limit: int) -> List[Dict]:
        """HTML에서 JSON 검색 결과 추출"""
        articles = []
        
        try:
            # 방법 1: script 태그에서 전체 pageProps 데이터 추출 (우선순위)
            soup = BeautifulSoup(html_content, 'html.parser')
            scripts = soup.find_all('script')
            
            for script in scripts:
                if script.string and 'pageProps' in script.string and 'results' in script.string:
                    try:
                        # script 내용에서 JSON 추출
                        script_content = script.string.strip()
                        
                        # pageProps 부분 찾기
                        pageProps_start = script_content.find('"pageProps":')
                        if pageProps_start > -1:
                            # JSON 객체의 시작점 찾기
                            json_start = script_content.find('{', pageProps_start)
                            if json_start > -1:
                                # 괄호 균형을 맞춰서 JSON 끝점 찾기
                                bracket_count = 0
                                json_end = json_start
                                
                                for i, char in enumerate(script_content[json_start:], json_start):
                                    if char == '{':
                                        bracket_count += 1
                                    elif char == '}':
                                        bracket_count -= 1
                                        if bracket_count == 0:
                                            json_end = i + 1
                                            break
                                
                                if json_end > json_start:
                                    try:
                                        json_str = script_content[json_start:json_end]
                                        page_data = json.loads(json_str)
                                        
                                        # page 데이터에서 results 찾기
                                        if 'page' in page_data:
                                            for page_key, page_value in page_data['page'].items():
                                                if isinstance(page_value, dict) and 'results' in page_value:
                                                    results = page_value['results']
                                                    if results and isinstance(results, list):
                                                        articles = self._parse_search_results_enhanced(results, limit)
                                                        if articles:
                                                            logger.info(f"script 태그에서 {len(articles)}개 결과 파싱 성공")
                                                            return articles
                                        
                                    except json.JSONDecodeError as e:
                                        logger.debug(f"페이지 데이터 JSON 파싱 실패: {e}")
                                        continue
                    except Exception as e:
                        logger.debug(f"script 파싱 실패: {e}")
                        continue
            
            # 방법 2: 기존 방식들 시도
            patterns = [
                r'"results":\s*(\[(?:[^[\]]+|\[[^\]]*\])*\])',
                r'"pageProps"[^{]*"results":\s*(\[(?:[^[\]]+|\[[^\]]*\])*\])',
                r'pageProps.*?results.*?(\[.*?\])',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html_content, re.DOTALL)
                for match in matches:
                    try:
                        cleaned_json = self._clean_json_string(match)
                        results = json.loads(cleaned_json)
                        
                        if results and isinstance(results, list) and len(results) > 0:
                            articles = self._parse_search_results_enhanced(results, limit)
                            if articles:
                                logger.info(f"정규식 패턴에서 {len(articles)}개 결과 파싱 성공")
                                return articles
                    except Exception as e:
                        logger.debug(f"JSON 파싱 시도 실패: {e}")
                        continue
            
            # 방법 3: HTML 직접 파싱 (fallback)
            logger.info("JSON 파싱 실패, HTML 직접 파싱으로 전환")
            articles = self._parse_html_fallback(html_content, limit)
                
        except Exception as e:
            logger.error(f"검색 결과 추출 실패: {e}")
            
        return articles
    
    def _clean_json_string(self, json_str: str) -> str:
        """JSON 문자열 정리"""
        # 끝나지 않은 문자열이나 객체 제거
        # 간단한 정리만 수행
        json_str = json_str.strip()
        
        # 배열이 제대로 닫혔는지 확인하고 수정
        open_brackets = json_str.count('[')
        close_brackets = json_str.count(']')
        
        if open_brackets > close_brackets:
            # 열린 괄호가 더 많으면 마지막 불완전한 객체를 제거하고 닫기
            # 마지막 완전한 객체를 찾기
            last_complete = json_str.rfind('"}')
            if last_complete > 0:
                json_str = json_str[:last_complete + 2] + ']'
            
        return json_str
    
    def _parse_search_results_enhanced(self, results: List[Dict], limit: int) -> List[Dict]:
        """JSON 검색 결과를 향상된 방식으로 파싱 (이미지 포함)"""
        articles = []
        
        for item in results[:limit]:
            try:
                if not isinstance(item, dict):
                    continue
                    
                title = item.get('title', '').strip()
                href = item.get('href', '').strip()
                description = item.get('description', '').strip()
                
                if not title or not href:
                    continue
                
                # URL 정규화
                if href.startswith('/'):
                    url = self.base_url + href
                elif not href.startswith('http'):
                    url = self.base_url + '/' + href.lstrip('/')
                else:
                    url = href
                
                # 이미지 URL 추출 - 더 많은 패턴 확인
                image_url = ''
                
                # 1. 직접적인 이미지 필드들
                image_fields = ['imageUrl', 'image', 'thumbnail', 'picture', 'photo']
                for field in image_fields:
                    if field in item:
                        image_data = item[field]
                        if isinstance(image_data, str):
                            image_url = image_data
                            break
                        elif isinstance(image_data, dict):
                            # 이미지 객체에서 URL 추출
                            for url_field in ['src', 'url', 'href', 'originalSrc']:
                                if url_field in image_data:
                                    image_url = image_data[url_field]
                                    break
                            if image_url:
                                break
                
                # 2. metadata에서 이미지 찾기
                if not image_url and 'metadata' in item:
                    metadata = item['metadata']
                    if isinstance(metadata, dict):
                        for field in image_fields:
                            if field in metadata:
                                image_data = metadata[field]
                                if isinstance(image_data, str):
                                    image_url = image_data
                                    break
                                elif isinstance(image_data, dict):
                                    for url_field in ['src', 'url', 'href', 'originalSrc']:
                                        if url_field in image_data:
                                            image_url = image_data[url_field]
                                            break
                                    if image_url:
                                        break
                
                # 3. 페이지에서 이미지 가져오기 (마지막 수단)
                if not image_url:
                    try:
                        # 실제 기사 페이지에서 이미지 가져오기 - 성능을 위해 제한적으로만 사용
                        if len(articles) < 3:  # 처음 3개 기사만
                            image_url = self._fetch_article_image(url)
                    except Exception as e:
                        logger.debug(f"기사 페이지에서 이미지 가져오기 실패: {e}")
                
                # 이미지 URL 정규화
                if image_url and not image_url.startswith('http'):
                    if image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    elif image_url.startswith('/'):
                        image_url = self.base_url + image_url
                
                # 메타데이터 처리
                metadata = item.get('metadata', {})
                content_type = metadata.get('contentType', '')
                subtype = metadata.get('subtype', '')
                last_updated = metadata.get('lastUpdated', '')
                
                # 날짜 변환
                published_date = ''
                if last_updated:
                    try:
                        timestamp = int(last_updated) / 1000
                        published_date = datetime.fromtimestamp(timestamp).strftime('%a, %d %b %Y %H:%M:%S GMT')
                    except:
                        published_date = str(last_updated)
                
                article = {
                    'title': title,
                    'url': url,
                    'summary': description,
                    'published_date': published_date,
                    'source': 'BBC News',
                    'category': subtype or content_type or 'news',
                    'scraped_at': datetime.now().isoformat(),
                    'relevance_score': 1,
                    'image_url': image_url
                }
                
                articles.append(article)
                
            except Exception as e:
                logger.warning(f"검색 결과 항목 파싱 실패: {e}")
                continue
        
        return articles
    
    def _parse_html_fallback(self, html_content: str, limit: int) -> List[Dict]:
        """HTML에서 직접 검색 결과 추출 (fallback)"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 여러 선택자로 검색 결과 찾기
            selectors = [
                'h2.sc-9d830f2a-3.duBczH',  # 메인 제목
                'h3.ssrcss-1drmzna-HeadingWrapper',  # 서브 제목
                'a[href*="/news/"], a[href*="/sport/"], a[href*="/audio/"]',  # 뉴스/스포츠/오디오 링크
            ]
            
            found_items = set()  # 중복 제거용
            
            for selector in selectors:
                elements = soup.select(selector)
                
                for element in elements:
                    try:
                        title = ''
                        url = ''
                        summary = ''
                        
                        if element.name in ['h2', 'h3']:
                            # 헤딩 요소인 경우
                            title = element.get_text(strip=True)
                            
                            # 링크 찾기
                            link_elem = element.find('a')
                            if not link_elem:
                                # 부모나 주변에서 링크 찾기
                                parent = element.find_parent(['div', 'article'])
                                if parent:
                                    link_elem = parent.find('a')
                            
                            if link_elem:
                                url = link_elem.get('href', '')
                            
                            # 설명 찾기 (주변 요소에서)
                            parent_container = element.find_parent(['div', 'article'])
                            if parent_container:
                                # 여러 방법으로 설명 찾기
                                desc_selectors = [
                                    'p',
                                    '.ssrcss-1q0x1qg-Paragraph',
                                    '[class*="description"]',
                                    '[class*="summary"]'
                                ]
                                for desc_sel in desc_selectors:
                                    desc_elem = parent_container.select_one(desc_sel)
                                    if desc_elem:
                                        summary = desc_elem.get_text(strip=True)
                                        break
                        
                        elif element.name == 'a':
                            # 링크 요소인 경우
                            url = element.get('href', '')
                            title = element.get_text(strip=True)
                            
                            # 부모 컨테이너에서 더 정확한 제목과 설명 찾기
                            parent = element.find_parent(['div', 'article'])
                            if parent:
                                # 더 좋은 제목 찾기
                                title_elem = parent.find(['h2', 'h3', 'h4'])
                                if title_elem:
                                    better_title = title_elem.get_text(strip=True)
                                    if len(better_title) > len(title):
                                        title = better_title
                                
                                # 설명 찾기
                                desc_elem = parent.find('p')
                                if desc_elem:
                                    summary = desc_elem.get_text(strip=True)
                        
                        # 기본 검증
                        if not title or not url or len(title) < 5:
                            continue
                        
                        # 이미지 URL 추출
                        image_url = ''
                        if parent:
                            # 이미지 찾기 - 여러 방법으로 시도
                            img_elem = parent.find('img')
                            if img_elem:
                                # src 또는 data-src 속성에서 이미지 URL 가져오기
                                image_url = img_elem.get('src', '') or img_elem.get('data-src', '') or img_elem.get('data-lazy-src', '')
                            
                            # BBC의 경우 picture 태그도 확인
                            if not image_url:
                                picture_elem = parent.find('picture')
                                if picture_elem:
                                    img_in_picture = picture_elem.find('img')
                                    if img_in_picture:
                                        image_url = img_in_picture.get('src', '') or img_in_picture.get('data-src', '')
                        
                        # 이미지 URL 정규화
                        if image_url and not image_url.startswith('http'):
                            if image_url.startswith('//'):
                                image_url = 'https:' + image_url
                            elif image_url.startswith('/'):
                                image_url = self.base_url + image_url
                        
                        # URL 정규화
                        if url.startswith('/'):
                            url = self.base_url + url
                        elif not url.startswith('http'):
                            continue
                        
                        # 중복 체크
                        item_key = (title, url)
                        if item_key in found_items:
                            continue
                        found_items.add(item_key)
                        
                        # 뉴스 관련 URL만 필터링
                        if not any(pattern in url for pattern in ['/news/', '/sport/', '/audio/', '/programmes/']):
                            continue
                        
                        article = {
                            'title': title,
                            'url': url,
                            'summary': summary[:300] if summary else '',  # 설명이 너무 길면 자르기
                            'published_date': '',
                            'source': 'BBC News',
                            'category': self._extract_category_from_url(url),
                            'scraped_at': datetime.now().isoformat(),
                            'relevance_score': 1,
                            'image_url': image_url
                        }
                        
                        articles.append(article)
                        
                        if len(articles) >= limit:
                            break
                            
                    except Exception as e:
                        logger.debug(f"HTML 요소 파싱 실패: {e}")
                        continue
                
                if len(articles) >= limit:
                    break
                    
        except Exception as e:
            logger.error(f"HTML fallback 처리 실패: {e}")
        
        return articles[:limit]
    
    def _fetch_article_image(self, article_url: str) -> str:
        """기사 페이지에서 이미지 URL 가져오기"""
        try:
            response = requests.get(article_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # BBC 기사 페이지의 메인 이미지 찾기
            selectors = [
                'img[data-component="image-block"]',
                'img[class*="hero"]',
                'img[class*="main"]',
                'picture img',
                '.story-body img:first-of-type',
                'article img:first-of-type'
            ]
            
            for selector in selectors:
                img = soup.select_one(selector)
                if img:
                    src = img.get('src', '') or img.get('data-src', '')
                    if src and 'bbc' in src:
                        return src
            
        except Exception as e:
            logger.debug(f"기사 이미지 가져오기 실패 {article_url}: {e}")
        
        return ''
    
    def _extract_category_from_url(self, url: str) -> str:
        """URL에서 카테고리 추출"""
        if '/sport/' in url:
            return 'sport'
        elif '/news/' in url:
            return 'news'
        elif '/audio/' in url:
            return 'audio'
        elif '/programmes/' in url:
            return 'programmes'
        else:
            return 'news'
    
    def get_latest_news(self, category: str = 'top_stories', limit: int = 10) -> List[Dict]:
        """카테고리별 최신 뉴스 - 일반 검색으로 대체"""
        # 카테고리에 맞는 키워드로 검색
        category_keywords = {
            'top_stories': 'breaking news',
            'world': 'world news',
            'uk': 'UK news',
            'business': 'business',
            'technology': 'technology',
            'science': 'science',
            'health': 'health'
        }
        
        keyword = category_keywords.get(category, 'news')
        return self.search_news(keyword, limit) 