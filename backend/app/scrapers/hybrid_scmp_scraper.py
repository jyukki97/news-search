#!/usr/bin/env python3

"""
하이브리드 SCMP 스크래퍼
HTTP 우선 → 실패시 Selenium 자동 사용
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict
from datetime import datetime
import logging
from urllib.parse import quote
import re
import time
import json

logger = logging.getLogger(__name__)

class HybridSCMPScraper:
    def __init__(self):
        self.base_url = "https://www.scmp.com"
        # SCMP GraphQL API 정보 (todoList3.md에서 확인된 실제 API)
        self.api_url = "https://apigw.scmp.com/content-delivery/v2"
        self.api_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
            'apikey': 'MyYvyg8M9RTaevVlcIRhN5yRIqqVssNY',
            'content-type': 'application/json',
            'origin': 'https://www.scmp.com',
            'referer': 'https://www.scmp.com/',
            'accept': '*/*',
            'accept-language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.selenium_available = self._check_selenium_availability()
    
    def _check_selenium_availability(self) -> bool:
        """Selenium 사용 가능 여부 확인"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            return True
        except ImportError:
            logger.info("Selenium이 설치되어 있지 않습니다. HTTP 방식만 사용합니다.")
            return False
    
    def search_news(self, query: str, limit: int = 10) -> List[Dict]:
        """하이브리드 뉴스 검색: GraphQL API → Selenium"""
        logger.info(f"SCMP 하이브리드 검색: {query}")
        
        # 1단계: GraphQL API 시도 (실제 SCMP API 사용)
        articles = self._search_with_graphql(query, limit)
        
        if articles and len(articles) >= 3:
            logger.info(f"GraphQL API로 {len(articles)}개 기사 찾음")
            return articles
        
        # 2단계: HTTP 폴백 시도
        http_articles = self._search_with_http(query, limit)
        if http_articles and len(http_articles) >= 3:
            logger.info(f"HTTP로 {len(http_articles)}개 기사 찾음")
            return http_articles
        
        # 3단계: Selenium 시도
        if self.selenium_available:
            logger.info("GraphQL/HTTP 결과 부족, Selenium으로 시도")
            selenium_articles = self._search_with_selenium(query, limit)
            
            if selenium_articles:
                logger.info(f"Selenium으로 {len(selenium_articles)}개 기사 찾음")
                return selenium_articles
        
        # 4단계: 폴백 - 홈페이지 최신 뉴스
        logger.info("모든 검색 실패, 홈페이지 최신 뉴스로 폴백")
        return self._get_homepage_articles(limit)
    
    def _search_with_graphql(self, query: str, limit: int) -> List[Dict]:
        """SCMP GraphQL API를 사용한 검색 (실제 API)"""
        try:
            logger.info(f"SCMP GraphQL API 검색 시도: {query}")
            
            # GraphQL 쿼리 구성 (todoList3.md에서 확인된 실제 구조)
            graphql_params = {
                "extensions": {
                    "persistedQuery": {
                        "sha256Hash": "05a3902acc7f34a4abcf1db1cb2b124fcc285f1e725554db4b2ce5959e5c8782",
                        "version": 1
                    }
                },
                "operationName": "searchResultPanelQuery",
                "variables": {
                    "articleTypeIds": [],
                    "contentTypes": ["ARTICLE", "VIDEO", "GALLERY"],
                    "first": min(limit * 2, 20),  # 더 많이 가져와서 필터링
                    "paywallTypeIds": [],
                    "query": query,
                    "sectionIds": []
                }
            }
            
            # GET 요청으로 전송 (실제 SCMP API 방식)
            import urllib.parse
            query_params = {
                'extensions': json.dumps(graphql_params['extensions']),
                'operationName': graphql_params['operationName'],
                'variables': json.dumps(graphql_params['variables'])
            }
            
            # URL 인코딩
            encoded_params = urllib.parse.urlencode(query_params)
            full_url = f"{self.api_url}?{encoded_params}"
            
            logger.info(f"GraphQL 요청 URL: {full_url[:100]}...")
            
            response = requests.get(full_url, headers=self.api_headers, timeout=10)
            response.raise_for_status()
            
            # 응답 파싱
            data = response.json()
            logger.info(f"GraphQL 응답 받음: {len(str(data))} bytes")
            
            # 검색 결과 추출
            articles = self._extract_graphql_results(data, query, limit)
            
            if articles:
                logger.info(f"GraphQL API로 {len(articles)}개 기사 추출 성공")
                return articles
            else:
                logger.info("GraphQL API 응답에서 기사 추출 실패")
                return []
            
        except Exception as e:
            logger.error(f"SCMP GraphQL API 검색 실패: {e}")
            return []
    
    def _extract_graphql_results(self, data: dict, query: str, limit: int) -> List[Dict]:
        """GraphQL 응답에서 기사 정보 추출"""
        articles = []
        
        try:
            # GraphQL 응답 구조 파싱
            if 'data' in data:
                search_data = data['data']
                
                # SCMP GraphQL API의 실제 응답 구조 사용
                edges = None
                
                # 실제 SCMP API 응답 구조: data.articleSearch.edges
                if 'articleSearch' in search_data and 'edges' in search_data['articleSearch']:
                    edges = search_data['articleSearch']['edges']
                    logger.info(f"GraphQL articleSearch에서 {len(edges)}개 기사 발견")
                else:
                    # 대안 경로들 시도
                    possible_paths = [
                        ['searchPanel', 'articles', 'edges'],
                        ['searchPanel', 'content', 'edges'],
                        ['search', 'articles', 'edges'],
                        ['search', 'results', 'edges'],
                        ['articles', 'edges'],
                        ['results', 'edges'],
                        ['edges']
                    ]
                    
                    for path in possible_paths:
                        current = search_data
                        try:
                            for key in path:
                                if key in current:
                                    current = current[key]
                                else:
                                    break
                            else:
                                # 모든 키가 존재하는 경우
                                if isinstance(current, list):
                                    edges = current
                                    logger.info(f"GraphQL 대안 경로 {path}에서 {len(edges)}개 기사 발견")
                                    break
                        except:
                            continue
                
                if edges:
                    for edge in edges[:limit]:
                        try:
                            node = edge.get('node', {})
                            if not node:
                                continue
                            
                            # SCMP GraphQL 응답의 실제 구조 사용
                            content = node.get('content', {})
                            if not content:
                                continue
                            
                            # 기사 정보 추출
                            title = content.get('headline', '') or content.get('title', '')
                            
                            # URL 구성 - urlAlias 사용
                            url_alias = content.get('urlAlias', '')
                            if url_alias:
                                url = self.base_url + url_alias
                            else:
                                url = content.get('url', '') or content.get('link', '')
                                if url and not url.startswith('http'):
                                    if url.startswith('/'):
                                        url = self.base_url + url
                                    else:
                                        url = self.base_url + '/' + url
                            
                            # 요약 추출
                            summary = ''
                            if 'summary' in content and content['summary']:
                                summary = content['summary'].get('text', '')
                            
                            if not title or not url:
                                continue
                            
                            # 이미지 URL 추출 - SCMP 구조에 맞게
                            image_url = ''
                            if 'images' in content and content['images'] and len(content['images']) > 0:
                                first_image = content['images'][0]
                                image_url = first_image.get('url', '')
                                if not image_url and 'size540x360' in first_image:
                                    image_url = first_image['size540x360'].get('url', '')
                            
                            if image_url and not image_url.startswith('http'):
                                if image_url.startswith('//'):
                                    image_url = 'https:' + image_url
                                elif image_url.startswith('/'):
                                    image_url = self.base_url + image_url
                            
                            # 날짜 추출 - SCMP 구조에 맞게
                            published_date = ''
                            published_timestamp = content.get('publishedDate')
                            if published_timestamp:
                                try:
                                    # 밀리초 타임스탬프를 초로 변환
                                    if isinstance(published_timestamp, (int, float)):
                                        timestamp = published_timestamp / 1000 if published_timestamp > 1e10 else published_timestamp
                                        published_date = datetime.fromtimestamp(timestamp).strftime('%a, %d %b %Y %H:%M:%S GMT')
                                except:
                                    pass
                            
                            if not published_date:
                                published_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
                            
                            # 카테고리 추출 - SCMP 구조에 맞게
                            category = 'General'
                            if 'sections' in content and content['sections']:
                                for section_group in content['sections']:
                                    if 'value' in section_group and section_group['value']:
                                        section_name = section_group['value'][0].get('name', '').lower()
                                        if 'sport' in section_name:
                                            category = 'sports'
                                        elif 'business' in section_name or 'economy' in section_name:
                                            category = 'business'
                                        elif 'tech' in section_name or 'technology' in section_name:
                                            category = 'technology'
                                        elif 'news' in section_name:
                                            category = 'news'
                                        else:
                                            category = section_name.title()
                                        break
                            
                            # 관련성 점수 계산
                            relevance_score = self._calculate_relevance(title, summary, query)
                            
                            article = {
                                'title': title[:200],
                                'url': url,
                                'summary': summary[:300] if summary else '',
                                'published_date': published_date,
                                'source': 'SCMP',
                                'category': category,
                                'scraped_at': datetime.now().isoformat(),
                                'relevance_score': relevance_score,
                                'image_url': image_url
                            }
                            
                            articles.append(article)
                            
                        except Exception as e:
                            logger.debug(f"GraphQL 기사 추출 실패: {e}")
                            continue
                
                else:
                    logger.info("GraphQL 응답에서 기사 목록을 찾을 수 없음")
                    if search_data:
                        logger.debug(f"응답 구조: {list(search_data.keys())}")
            
        except Exception as e:
            logger.error(f"GraphQL 결과 파싱 실패: {e}")
        
        # 관련성 순으로 정렬
        articles.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return articles[:limit]
    
    def _calculate_relevance(self, title: str, summary: str, query: str) -> float:
        """검색어와 기사의 관련성 점수 계산"""
        if not query:
            return 1.0
        
        query_words = query.lower().split()
        title_lower = title.lower()
        summary_lower = summary.lower()
        
        score = 0.0
        
        for word in query_words:
            # 제목에서 발견 (높은 점수)
            if word in title_lower:
                score += 3.0
            # 요약에서 발견 (중간 점수)
            elif word in summary_lower:
                score += 1.0
        
        # 정규화 (0-1 범위)
        max_possible_score = len(query_words) * 3.0
        return min(score / max_possible_score, 1.0) if max_possible_score > 0 else 0.0
    
    def _search_with_http(self, query: str, limit: int) -> List[Dict]:
        """HTTP 기반 검색 (실제 SCMP 검색 URL 사용)"""
        try:
            # SCMP 검색 패턴들 (실제 작동 확인됨)
            if 'sport' in query.lower():
                # 스포츠 관련 검색은 topics/sports 사용
                search_patterns = [
                    f"https://www.scmp.com/topics/sports",
                    f"https://www.scmp.com/news?search={quote(query)}",
                    f"https://www.scmp.com/search/{quote(query)}"
                ]
            else:
                # 일반 검색
                search_patterns = [
                    f"https://www.scmp.com/news?search={quote(query)}",
                    f"https://www.scmp.com/search/{quote(query)}",
                    f"https://www.scmp.com/search?query={quote(query)}"
                ]
            
            for search_url in search_patterns:
                try:
                    logger.info(f"SCMP 검색 시도: {search_url}")
                    response = requests.get(search_url, headers=self.headers, timeout=10)
                    response.raise_for_status()
                    
                    extracted_articles = self._extract_scmp_search_results(response.text, limit, query)
                    if extracted_articles:
                        # 쿼리와 관련성이 높은 기사들만 필터링
                        relevant_articles = self._filter_relevant_articles(extracted_articles, query)
                        if relevant_articles:
                            logger.info(f"SCMP HTTP 검색 결과: {len(relevant_articles)}개 기사 찾음")
                            return relevant_articles
                except Exception as e:
                    logger.debug(f"SCMP 검색 URL 실패 {search_url}: {e}")
                    continue
            
            # 모든 검색 패턴 실패시
            logger.info("SCMP HTTP 검색 실패")
            return []
            
        except Exception as e:
            logger.debug(f"HTTP 검색 실패: {e}")
            return []
    
    def _extract_scmp_search_results(self, html_content: str, limit: int, query: str = '') -> List[Dict]:
        """SCMP 검색 결과에서 기사 추출 (개선된 파싱)"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # SCMP 기사 링크 패턴들 (테스트 확인됨)
            patterns = [
                'a[href*="/article/"]',
                'a[href*="scmp.com"]', 
                'a[href*="/news/"]'
            ]
            
            found_urls = set()
            
            for pattern in patterns:
                links = soup.select(pattern)
                
                for link in links:
                    try:
                        href = link.get('href', '')
                        title = link.get_text(strip=True)
                        
                        # URL 정규화
                        if href.startswith('/'):
                            href = self.base_url + href
                        elif not href.startswith('http'):
                            continue
                        
                        # 기본 검증
                        if (not title or len(title) < 15 or 
                            href in found_urls or 
                            'scmp.com' not in href):
                            continue
                        
                        found_urls.add(href)
                        
                        # SCMP 이미지 추출 - 개선된 방법
                        image_url = self._extract_scmp_image_improved(link, href)
                        
                        # SCMP 날짜 추출
                        published_date = self._extract_scmp_date(link, href)
                        
                        # 카테고리 추출
                        category = self._extract_category_from_url(href)
                        
                        article = {
                            'title': title,
                            'url': href,
                            'summary': '',  # 검색 결과에서는 요약 생략
                            'published_date': published_date,
                            'source': 'SCMP',
                            'category': category,
                            'scraped_at': datetime.now().isoformat(),
                            'relevance_score': 1,
                            'image_url': image_url
                        }
                        
                        articles.append(article)
                        
                        if len(articles) >= limit:
                            break
                            
                    except Exception as e:
                        logger.debug(f"SCMP 링크 파싱 실패: {e}")
                        continue
                
                if len(articles) >= limit:
                    break
                    
        except Exception as e:
            logger.error(f"SCMP 검색 결과 HTML 파싱 실패: {e}")
        
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
    
    def _extract_scmp_image_improved(self, link_elem, article_url: str) -> str:
        """개선된 SCMP 이미지 추출 - 메타 태그 우선"""
        try:
            # 1. 기사 페이지에서 메타 태그 이미지 추출
            response = requests.get(article_url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # OpenGraph 이미지
                og_image = soup.find('meta', property='og:image')
                if og_image and og_image.get('content'):
                    return og_image['content']
                
                # Twitter 이미지
                twitter_image = soup.find('meta', name='twitter:image')
                if twitter_image and twitter_image.get('content'):
                    return twitter_image['content']
                
                # 기사 본문의 첫 번째 이미지
                article_img = soup.find('article')
                if article_img:
                    img = article_img.find('img')
                    if img and img.get('src'):
                        src = img['src']
                        if src.startswith('//'):
                            return 'https:' + src
                        elif src.startswith('/'):
                            return self.base_url + src
                        return src
                        
        except Exception as e:
            logger.debug(f"SCMP 메타 이미지 추출 실패: {e}")
        
        # 2. 폴백: 기존 방법 사용
        return self._extract_scmp_image(link_elem, article_url)
    
    def _extract_scmp_image(self, link_elem, article_url: str) -> str:
        """SCMP 기사에서 고유한 이미지 추출 (기존 로직)"""
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
            
            # 2. 링크의 직접 부모에서 이미지 찾기
            if not image_url:
                parent = link_elem.find_parent()
                if parent:
                    img_elems = parent.find_all('img')
                    for img_elem in img_elems:
                        for attr in ['src', 'data-src', 'data-lazy-src', 'data-original']:
                            img_src = img_elem.get(attr, '')
                            if img_src and self._is_valid_scmp_image(img_src):
                                image_url = img_src
                                break
                        if image_url:
                            break
            
            # 3. 형제 요소에서 이미지 찾기
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
                
        except Exception as e:
            logger.debug(f"SCMP 이미지 추출 실패: {e}")
        
        return image_url
    
    def _is_valid_scmp_image(self, url: str) -> bool:
        """SCMP 이미지가 유효하고 고유한지 확인"""
        if not url or len(url) < 10:
            return False
        
        # 제외할 이미지 패턴들
        exclude_patterns = [
            'logo',
            'avatar',
            'icon',
            'placeholder',
            'default',
            'blank',
            'spacer',
            'tracking',
            'pixel',
            'scmp-logo',
            'facebook',
            'twitter',
            'linkedin',
            'whatsapp',
            'telegram',
            'instagram'
        ]
        
        url_lower = url.lower()
        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False
        
        # 유효한 이미지 확장자 확인
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        if any(ext in url_lower for ext in valid_extensions):
            return True
        
        # SCMP CDN 패턴 확인
        if any(domain in url for domain in ['scmp.com', 'scmpcdn.com', 'img.scmp.com']):
            return True
        
        return False
    
    def _extract_scmp_date(self, element, url: str) -> str:
        """SCMP 날짜 추출 (기존 로직)"""
        try:
            # 1. 요소에서 날짜 텍스트 찾기
            date_selectors = [
                '.published-date',
                '.date',
                '.timestamp',
                'time',
                '[datetime]',
                '.meta-date'
            ]
            
            for selector in date_selectors:
                date_elem = element.find(selector)
                if date_elem:
                    date_text = date_elem.get('datetime') or date_elem.get_text(strip=True)
                    if date_text:
                        return self._format_date(date_text)
            
            # 2. URL에서 날짜 패턴 찾기
            date_patterns = [
                r'/(\d{4})/(\d{1,2})/(\d{1,2})/',
                r'/article/(\d+)/',
                r'-(\d{4})-(\d{1,2})-(\d{1,2})'
            ]
            
            for pattern in date_patterns:
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
            logger.debug(f"SCMP 날짜 추출 실패: {e}")
        
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    def _format_date(self, date_str: str) -> str:
        """날짜 문자열을 GMT 형식으로 변환"""
        try:
            # 다양한 날짜 형식 시도
            date_formats = [
                '%Y-%m-%d',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d %H:%M:%S',
                '%d %b %Y',
                '%b %d, %Y',
                '%d/%m/%Y',
                '%m/%d/%Y'
            ]
            
            for fmt in date_formats:
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                except:
                    continue
                    
        except Exception as e:
            logger.debug(f"날짜 형식 변환 실패: {e}")
        
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    def _search_with_selenium(self, query: str, limit: int) -> List[Dict]:
        """Selenium 기반 검색"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument(f'--user-agent={self.headers["User-Agent"]}')
            
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(10)
            
            articles = []
            
            try:
                search_url = f"https://www.scmp.com/search?query={quote(query)}"
                driver.get(search_url)
                
                # JavaScript 로딩 대기
                time.sleep(5)
                
                # 검색 결과 찾기
                selectors = [
                    'article',
                    '[class*="article"]',
                    '[class*="story"]',
                    'a[href*="/news/"]',
                    'a[href*="/business/"]',
                    'a[href*="/sport/"]'
                ]
                
                for selector in selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        
                        for element in elements[:limit]:
                            article = self._extract_article_from_element(element, driver)
                            if article and article not in articles:
                                articles.append(article)
                                
                                if len(articles) >= limit:
                                    break
                        
                        if articles:
                            break
                            
                    except Exception as e:
                        continue
                
                return articles
                
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error(f"Selenium 검색 실패: {e}")
            return []
    
    def _extract_article_from_element(self, element, driver) -> Dict:
        """Selenium 요소에서 기사 정보 추출"""
        try:
            # 제목 추출
            title = ""
            try:
                title = element.text.strip()
                if not title:
                    title = element.get_attribute('textContent').strip()
            except:
                pass
            
            # URL 추출
            url = ""
            try:
                if element.tag_name == 'a':
                    url = element.get_attribute('href')
                else:
                    link = element.find_element(By.TAG_NAME, 'a')
                    url = link.get_attribute('href')
            except:
                pass
            
            # 기본 검증
            if not title or not url or len(title) < 10:
                return None
            
            # URL 정규화
            if url.startswith('/'):
                url = self.base_url + url
            
            # SCMP 도메인 확인
            if 'scmp.com' not in url:
                return None
            
            return {
                'title': title[:200],
                'url': url,
                'summary': '',
                'published_date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),
                'source': 'SCMP',
                'category': self._extract_category_from_url(url),
                'scraped_at': datetime.now().isoformat(),
                'relevance_score': 0.5,
                'image_url': ''  # Selenium에서는 이미지 추출 생략
            }
            
        except Exception as e:
            return None
    
    def _get_homepage_articles(self, limit: int) -> List[Dict]:
        """홈페이지에서 최신 뉴스 가져오기 (폴백)"""
        try:
            response = requests.get(self.base_url, headers=self.headers, timeout=5)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = []
            
            # SCMP 홈페이지에서 기사 링크 찾기
            selectors = [
                'h3 a[href*="/news/"]',
                'h2 a[href*="scmp.com"]',
                'a[href*="/article/"][href*="/"]',
                '.headline a',
                '.entry-title a',
                'h4 a[href*="/"]'
            ]
            
            found_urls = set()
            
            for selector in selectors:
                links = soup.select(selector)
                
                for link in links:
                    href = link.get('href', '')
                    title = link.get_text(strip=True)
                    
                    if not href or not title or len(title) < 10:
                        continue
                    
                    if href.startswith('/'):
                        href = self.base_url + href
                    
                    if 'scmp.com' not in href or href in found_urls:
                        continue
                    found_urls.add(href)
                    
                    # 이미지 추출
                    image_url = self._extract_scmp_image(link, href)
                    if image_url:
                        if image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        elif image_url.startswith('/'):
                            image_url = self.base_url + image_url
                    
                    article = {
                        'title': title,
                        'url': href,
                        'summary': '',
                        'published_date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),
                        'source': 'SCMP',
                        'category': self._extract_category_from_url(href),
                        'scraped_at': datetime.now().isoformat(),
                        'relevance_score': 1,
                        'image_url': image_url
                    }
                    
                    articles.append(article)
                    if len(articles) >= limit:
                        break
                
                if len(articles) >= limit:
                    break
            
            return articles
            
        except Exception as e:
            logger.error(f"홈페이지 폴백 실패: {e}")
            return []
    
    def _extract_category_from_url(self, url: str) -> str:
        """URL에서 카테고리 추출"""
        try:
            if '/news/' in url:
                return 'news'
            elif '/business/' in url or '/economy/' in url:
                return 'business'
            elif '/sport/' in url:
                return 'sports'
            elif '/tech/' in url or '/technology/' in url:
                return 'technology'
            elif '/lifestyle/' in url:
                return 'lifestyle'
            elif '/culture/' in url:
                return 'culture'
            elif '/opinion/' in url:
                return 'opinion'
            else:
                return 'General'
        except:
            return 'General'
    
    def get_latest_news(self, category: str = 'news', limit: int = 10) -> List[Dict]:
        """카테고리별 최신 뉴스 가져오기 - 실제 SCMP 카테고리 페이지 사용"""
        try:
            logger.info(f"SCMP 실제 카테고리별 뉴스 요청: {category}")
            
            # 실제 SCMP 카테고리별 URL들
            category_urls = {
                'all': 'https://www.scmp.com',
                'news': 'https://www.scmp.com/news',
                'business': 'https://www.scmp.com/business',
                'sports': 'https://www.scmp.com/sport',
                'sport': 'https://www.scmp.com/sport',
                'technology': 'https://www.scmp.com/tech',
                'tech': 'https://www.scmp.com/tech',
                'entertainment': 'https://www.scmp.com/lifestyle/entertainment',
                'health': 'https://www.scmp.com/lifestyle/health-wellness',
                'world': 'https://www.scmp.com/news/world',
                'china': 'https://www.scmp.com/news/china',
                'hongkong': 'https://www.scmp.com/news/hong-kong',
                'lifestyle': 'https://www.scmp.com/lifestyle'
            }
            
            url = category_urls.get(category, category_urls['news'])
            logger.info(f"SCMP 카테고리 페이지 접근: {url}")
            
            # 실제 카테고리 페이지에서 기사 추출
            try:
                response = requests.get(url, headers=self.headers, timeout=15)
                response.raise_for_status()
                
                articles = self._extract_scmp_category_articles(response.text, limit, category)
                
                if articles:
                    logger.info(f"SCMP {category} 카테고리에서 {len(articles)}개 기사 추출")
                    return articles
                else:
                    logger.info(f"SCMP {category} 카테고리 추출 실패, 검색으로 폴백")
                    
            except Exception as e:
                logger.warning(f"SCMP 카테고리 페이지 접근 실패: {e}, 검색으로 폴백")
            
            # 폴백: 카테고리별 키워드 검색 (기존 로직)
            category_keywords = {
                'news': 'Hong Kong China news',
                'business': 'business economy markets',
                'sports': 'sports football Hong Kong',
                'sport': 'sports football Hong Kong',
                'technology': 'technology tech innovation',
                'tech': 'technology tech innovation',
                'health': 'health wellness medical',
                'entertainment': 'entertainment celebrity culture',
                'world': 'world international news',
                'china': 'China Beijing',
                'hongkong': 'Hong Kong'
            }
            
            keyword = category_keywords.get(category, 'Hong Kong news')
            logger.info(f"SCMP 검색 폴백: {category} -> {keyword}")
            
            return self.search_news(keyword, limit)
            
        except Exception as e:
            logger.error(f"SCMP 카테고리별 뉴스 가져오기 실패: {e}")
            # 최종 폴백: 홈페이지 기사
            return self._get_homepage_articles(limit)
    
    def _extract_scmp_category_articles(self, html_content: str, limit: int, category: str) -> List[Dict]:
        """SCMP 카테고리 페이지에서 기사 추출"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # SCMP 기사 링크 선택자들
            article_selectors = [
                # 메인 기사 링크들
                'h2 a[href*="/article/"]',
                'h3 a[href*="/article/"]',
                'h4 a[href*="/article/"]',
                # 기사 컨테이너들
                'article a[href*="/article/"]',
                '.story a[href*="/article/"]',
                '.post a[href*="/article/"]',
                # 일반적인 SCMP 기사 링크들
                'a[href*="scmp.com"][href*="/article/"]',
                'a[href*="/news/"][href*="/article/"]',
                'a[href*="/business/"][href*="/article/"]',
                'a[href*="/sport/"][href*="/article/"]'
            ]
            
            found_urls = set()
            
            for selector in article_selectors:
                try:
                    links = soup.select(selector)
                    logger.debug(f"SCMP {selector}: {len(links)}개 링크 발견")
                    
                    for link in links:
                        try:
                            title = link.get_text(strip=True)
                            url = link.get('href', '')
                            
                            # 기본 검증
                            if not title or len(title) < 15:
                                continue
                                
                            if not url or '/article/' not in url:
                                continue
                                
                            # URL 정규화
                            if url.startswith('/'):
                                url = 'https://www.scmp.com' + url
                            elif not url.startswith('http'):
                                url = 'https://www.scmp.com/' + url
                            
                            # SCMP URL 확인
                            if 'scmp.com' not in url:
                                continue
                                
                            # 중복 확인
                            if url in found_urls:
                                continue
                            found_urls.add(url)
                            
                            # 불필요한 링크 필터링
                            if any(skip in url.lower() for skip in [
                                '/search', '/login', '/register', '/subscribe', 
                                '/contact', '/about', '/terms', '/privacy'
                            ]):
                                continue
                            
                            # 링크 주변에서 정보 추출
                            parent = link.parent
                            context = parent.parent if parent and parent.parent else parent if parent else link
                            
                            # 요약 추출
                            summary = self._extract_scmp_summary(context, title)
                            
                            # 이미지 추출 (기존 로직 사용)
                            image_url = self._extract_scmp_image(link, url)
                            
                            # 날짜 추출 (기존 로직 사용)
                            published_date = self._extract_scmp_date(context, url)
                            
                            # 카테고리 추출
                            article_category = self._extract_category_from_url(url) or category
                            
                            article = {
                                'title': title,
                                'url': url,
                                'summary': summary[:300] if summary else title[:200],
                                'published_date': published_date,
                                'source': 'SCMP',
                                'category': article_category,
                                'scraped_at': datetime.now().isoformat(),
                                'relevance_score': 1,
                                'image_url': image_url
                            }
                            
                            articles.append(article)
                            
                            if len(articles) >= limit:
                                break
                                
                        except Exception as e:
                            logger.debug(f"SCMP 개별 기사 처리 실패: {e}")
                            continue
                    
                    if len(articles) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug(f"SCMP selector {selector} 처리 실패: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"SCMP 카테고리 HTML 파싱 실패: {e}")
        
        return articles[:limit]
    
    def _extract_scmp_summary(self, element, title: str) -> str:
        """SCMP 기사에서 요약 추출"""
        summary = ''
        
        try:
            if hasattr(element, 'find_all'):
                # SCMP 요약 패턴들
                summary_selectors = [
                    'p',
                    '.excerpt', 
                    '.summary',
                    '.description',
                    '.story-summary'
                ]
                
                for selector in summary_selectors:
                    elements = element.find_all(selector)
                    
                    for elem in elements:
                        text = elem.get_text(strip=True)
                        
                        # 유효한 요약인지 확인
                        if (len(text) > 30 and len(text) < 500 and
                            text != title and
                            not text.startswith('SCMP') and
                            not text.startswith('South China Morning Post') and
                            not text.lower().startswith('click here') and
                            not text.lower().startswith('read more') and
                            'scmp.com' not in text.lower()):
                            
                            summary = text
                            break
                    
                    if summary:
                        break
                        
        except Exception as e:
            logger.debug(f"SCMP 요약 추출 실패: {e}")
        
        return summary
    
    def _extract_scmp_date(self, element, url: str) -> str:
        """SCMP 기사에서 날짜 추출"""
        try:
            # 기존 날짜 추출 로직 사용
            if hasattr(element, 'get_text'):
                text = element.get_text()
                
                # SCMP 날짜 패턴들
                date_patterns = [
                    r'(\d{1,2}\s+\w+\s+\d{4})',  # 17 July 2025
                    r'(\w+\s+\d{1,2},\s*\d{4})',  # July 17, 2025
                    r'(\d{1,2}/\d{1,2}/\d{4})',  # 17/07/2025
                    r'(\d{4}-\d{1,2}-\d{1,2})'   # 2025-07-17
                ]
                
                for pattern in date_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        try:
                            date_str = match.group(0)
                            for fmt in ['%d %B %Y', '%B %d, %Y', '%d %b %Y', '%b %d, %Y', '%d/%m/%Y', '%Y-%m-%d']:
                                try:
                                    date_obj = datetime.strptime(date_str, fmt)
                                    return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                                except:
                                    continue
                        except:
                            continue
            
            # URL에서 날짜 추출
            url_match = re.search(r'/article/(\d+)', url)
            if url_match:
                # SCMP 기사 ID에서 날짜 추출 시도 (추후 구현 가능)
                pass
                
        except Exception as e:
            logger.debug(f"SCMP 날짜 추출 실패: {e}")
        
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    def _extract_scmp_image(self, link_elem, article_url: str) -> str:
        """SCMP 기사에서 이미지 추출 (기존 로직 재사용)"""
        try:
            # 기존 이미지 추출 로직을 재사용
            # 여기서는 간단히 처리
            if hasattr(link_elem, 'find'):
                img_elem = link_elem.find('img')
                if img_elem:
                    for attr in ['src', 'data-src', 'data-lazy-src']:
                        img_src = img_elem.get(attr, '')
                        if img_src and ('scmp.com' in img_src or img_src.startswith('//')):
                            if img_src.startswith('//'):
                                return 'https:' + img_src
                            elif img_src.startswith('/'):
                                return 'https://www.scmp.com' + img_src
                            return img_src
        except Exception as e:
            logger.debug(f"SCMP 이미지 추출 실패: {e}")
        
        return '' 