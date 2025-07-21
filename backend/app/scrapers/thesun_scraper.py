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
        # The Sun은 Google Site Search를 사용하는 것으로 보임
        self.search_url = "https://www.google.co.uk/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
    def search_news(self, query: str, limit: int = 10) -> List[Dict]:
        """The Sun에서 뉴스 검색 - Google Site Search 사용"""
        try:
            logger.info("The Sun search via Google: {}".format(query))
            
            # Google Site Search 사용 (site:thesun.co.uk query)
            search_query = f"site:thesun.co.uk {query}"
            params = {
                'q': search_query,
                'tbm': 'nws',  # news search
                'num': min(limit * 2, 20)  # 더 많은 결과 요청
            }
            
            response = requests.get(self.search_url, params=params, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            # Google 검색 결과에서 The Sun 링크들 추출
            articles = self._extract_google_thesun_results(response.text, limit, query)
            
            logger.info("The Sun found {} search results via Google".format(len(articles)))
            return articles
            
        except Exception as e:
            logger.error("The Sun search via Google failed: {}".format(e))
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
        """카테고리별 최신 뉴스 - 실제 The Sun 카테고리 페이지 사용"""
        try:
            logger.info(f"The Sun 실제 카테고리별 뉴스 요청: {category}")
            
            # health, sports, entertainment, tech 카테고리는 바로 검색 모드 사용 (카테고리 페이지 파싱이 어려우므로)
            if category == 'health':
                logger.info("The Sun health 카테고리 - 직접 검색 모드 사용")
                return self.search_news('health NHS medical doctor UK healthcare hospital', limit)
            elif category in ['sport', 'sports']:
                logger.info("The Sun sport 카테고리 - 직접 검색 모드 사용")
                return self.search_news('football premier league sport cricket rugby tennis UK', limit)
            elif category in ['entertainment', 'celebrity']:
                logger.info("The Sun entertainment 카테고리 - 직접 검색 모드 사용")
                return self.search_news('celebrity entertainment showbiz TV film music UK', limit)
            elif category in ['technology', 'tech']:
                logger.info("The Sun tech 카테고리 - 직접 검색 모드 사용")
                return self.search_news('technology tech gadgets iPhone Android apps UK', limit)
            
            # 실제 The Sun 카테고리별 URL들 (사용자 제공 URL 포함)
            category_urls = {
                'all': 'https://www.thesun.co.uk',
                'news': 'https://www.thesun.co.uk/news/',
                'sports': 'https://www.thesun.co.uk/sport/',
                'sport': 'https://www.thesun.co.uk/sport/',
                'business': 'https://www.thesun.co.uk/money/',
                'technology': 'https://www.thesun.co.uk/tech/',  # 사용자 제공 URL
                'tech': 'https://www.thesun.co.uk/tech/',
                'health': 'https://www.thesun.co.uk/health/',
                'entertainment': 'https://www.thesun.co.uk/fabulous/fabulous-celebrity/',  # 사용자 제공 URL
                'celebrity': 'https://www.thesun.co.uk/fabulous/fabulous-celebrity/',
                'world': 'https://www.thesun.co.uk/news/worldnews/',
                'politics': 'https://www.thesun.co.uk/news/politics/',
                'travel': 'https://www.thesun.co.uk/travel/'
            }
            
            url = category_urls.get(category, category_urls['news'])
            logger.info(f"The Sun 카테고리 페이지 접근: {url}")
            
            # 실제 카테고리 페이지에서 기사 추출
            try:
                response = requests.get(url, headers=self.headers, timeout=15)
                response.raise_for_status()
                
                articles = self._extract_thesun_category_articles(response.text, limit, category)
                
                if articles:
                    logger.info(f"The Sun {category} 카테고리에서 {len(articles)}개 기사 추출")
                    return articles
                else:
                    logger.info(f"The Sun {category} 카테고리 추출 실패, 검색으로 폴백")
                    
            except Exception as e:
                logger.warning(f"The Sun 카테고리 페이지 접근 실패: {e}, 검색으로 폴백")
            
            # 폴백: 카테고리별 키워드 검색 (기존 로직 개선)
            category_keywords = {
                'news': 'breaking news UK',
                'sports': 'football premier league',
                'sport': 'football premier league',
                'business': 'money economy UK',
                'technology': 'tech innovation',
                'tech': 'tech innovation',
                'health': 'health NHS medical',
                'entertainment': 'celebrity showbiz TV',
                'world': 'world international news',
                'politics': 'politics UK government'
            }
            
            keyword = category_keywords.get(category, 'breaking news')
            logger.info(f"The Sun 검색 폴백: {category} -> {keyword}")
            
            return self.search_news(keyword, limit)
            
        except Exception as e:
            logger.error(f"The Sun 카테고리별 뉴스 실패: {e}")
            return []
    
    def _extract_thesun_category_articles(self, html_content: str, limit: int, category: str) -> List[Dict]:
        """The Sun 카테고리 페이지에서 기사 추출 - 개선된 로직"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            logger.info(f"The Sun HTML 길이: {len(html_content)}")
            
            # The Sun 기사 링크를 위한 개선된 선택자들
            article_selectors = [
                # 실제 The Sun 웹사이트 구조 기반 선택자들
                'h2 a[href*="/sport/"]',
                'h3 a[href*="/sport/"]', 
                'h4 a[href*="/sport/"]',
                'h2 a[href*="/health/"]',
                'h3 a[href*="/health/"]',
                'h4 a[href*="/health/"]',
                # 더 구체적인 The Sun 선택자들
                'a[href*="thesun.co.uk/sport/"]',
                'a[href*="thesun.co.uk/health/"]',
                'a[href*="thesun.co.uk/news/"]',
                # 일반적인 링크들 (thesun.co.uk 포함)
                'a[href*="thesun.co.uk"][href*="/"]'
            ]
            
            found_urls = set()
            
            for selector in article_selectors:
                try:
                    links = soup.select(selector)
                    logger.info(f"The Sun {selector}: {len(links)}개 링크 발견")
                    
                    for link in links:
                        try:
                            title = link.get_text(strip=True)
                            url = link.get('href', '')
                            
                            # 기본 검증 강화
                            if not title or len(title) < 10:
                                continue
                                
                            if not url:
                                continue
                                
                            # URL 정규화
                            if url.startswith('/'):
                                url = 'https://www.thesun.co.uk' + url
                            elif not url.startswith('http'):
                                continue
                            
                            # The Sun URL 확인
                            if 'thesun.co.uk' not in url:
                                continue
                            
                            # 카테고리 필터링 개선 (요청된 카테고리와 맞는지 확인)
                            if category == 'health' and '/health/' not in url:
                                continue
                            elif category in ['sport', 'sports'] and '/sport/' not in url:
                                continue
                                
                            # 중복 확인
                            if url in found_urls:
                                continue
                            found_urls.add(url)
                            
                            # 불필요한 링크 필터링 강화
                            skip_patterns = [
                                '/search', '/login', '/register', '/subscribe', 
                                '/contact', '/about', '/terms', '/privacy',
                                '/author/', '/tag/', '/feed/', '/sign-up',
                                '/editorial-complaints', '/policies', '/cookie'
                            ]
                            
                            if any(skip in url.lower() for skip in skip_patterns):
                                continue
                                
                            # 불필요한 제목들 필터링 강화
                            skip_titles = [
                                'follow us', 'subscribe', 'newsletter', 'login',
                                'register', 'contact us', 'privacy policy',
                                'terms of service', 'cookie policy', 'sign up',
                                'editorial complaints', 'policies and ethics'
                            ]
                            
                            if any(skip in title.lower() for skip in skip_titles):
                                continue
                            
                            # 링크 주변에서 정보 추출
                            parent = link.parent
                            context = parent.parent if parent and parent.parent else parent if parent else link
                            
                            # 요약 추출
                            summary = self._extract_thesun_summary(context, title)
                            
                            # 이미지 추출
                            image_url = self._extract_thesun_image(link, url)
                            
                            # 날짜 추출
                            published_date = self._extract_thesun_date(context, url)
                            
                            # 카테고리 추출
                            article_category = self._extract_thesun_category_from_url(url) or category
                            
                            article = {
                                'title': title,
                                'url': url,
                                'summary': summary[:300] if summary else title[:200],
                                'published_date': published_date,
                                'source': 'The Sun',
                                'category': article_category,
                                'scraped_at': datetime.now().isoformat(),
                                'relevance_score': 1,
                                'image_url': image_url
                            }
                            
                            articles.append(article)
                            logger.info(f"The Sun 기사 추가: {title[:50]}...")
                            
                            if len(articles) >= limit:
                                break
                                
                        except Exception as e:
                            logger.debug(f"The Sun 개별 기사 처리 실패: {e}")
                            continue
                    
                    if len(articles) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug(f"The Sun selector {selector} 처리 실패: {e}")
                    continue
            
            logger.info(f"The Sun 총 {len(articles)}개 기사 추출됨")
                    
        except Exception as e:
            logger.error(f"The Sun 카테고리 HTML 파싱 실패: {e}")
        
        return articles[:limit]
    
    def _extract_thesun_summary(self, element, title: str) -> str:
        """The Sun 기사에서 요약 추출"""
        summary = ''
        
        try:
            if hasattr(element, 'find_all'):
                summary_selectors = ['p', '.excerpt', '.summary', '.description']
                
                for selector in summary_selectors:
                    elements = element.find_all(selector)
                    
                    for elem in elements:
                        text = elem.get_text(strip=True)
                        
                        if (len(text) > 30 and len(text) < 500 and
                            text != title and
                            not text.startswith('The Sun') and
                            not text.lower().startswith('click here') and
                            'thesun.co.uk' not in text.lower()):
                            
                            summary = text
                            break
                    
                    if summary:
                        break
                        
        except Exception as e:
            logger.debug(f"The Sun 요약 추출 실패: {e}")
        
        return summary
    
    def _extract_thesun_image(self, link_elem, article_url: str) -> str:
        """The Sun 기사에서 이미지 추출"""
        try:
            if hasattr(link_elem, 'find'):
                img_elem = link_elem.find('img')
                if img_elem:
                    for attr in ['src', 'data-src', 'data-lazy-src']:
                        img_src = img_elem.get(attr, '')
                        if img_src and ('thesun.co.uk' in img_src or img_src.startswith('//')):
                            if img_src.startswith('//'):
                                return 'https:' + img_src
                            elif img_src.startswith('/'):
                                return 'https://www.thesun.co.uk' + img_src
                            return img_src
        except Exception as e:
            logger.debug(f"The Sun 이미지 추출 실패: {e}")
        
        return ''
    
    def _extract_thesun_date(self, element, url: str) -> str:
        """The Sun 기사에서 날짜 추출"""
        try:
            if hasattr(element, 'get_text'):
                text = element.get_text()
                
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
                            
        except Exception as e:
            logger.debug(f"The Sun 날짜 추출 실패: {e}")
        
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    def _extract_thesun_category_from_url(self, url: str) -> str:
        """The Sun URL에서 카테고리 추출 - 업데이트된 URL 패턴 포함"""
        try:
            if '/sport/' in url:
                return 'sports'
            elif '/money/' in url:
                return 'business'
            elif '/tech/' in url:
                return 'technology'
            elif '/health/' in url:
                return 'health'
            elif '/fabulous/fabulous-celebrity/' in url or '/celebrity/' in url:
                return 'entertainment'
            elif '/tv/' in url or '/showbiz/' in url or '/entertainment/' in url:
                return 'entertainment'
            elif '/news/' in url:
                return 'news'
            else:
                return 'news'
        except:
            return 'news' 

    def _extract_google_thesun_results(self, html_content: str, limit: int, query: str = '') -> List[Dict]:
        """Google 검색 결과에서 The Sun 기사들 추출"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Google 뉴스 검색 결과 선택자들
            result_selectors = [
                'div[data-ved] h3 a',  # 일반적인 Google 검색 결과
                '.g h3 a',  # Google 검색 결과
                'a[href*="thesun.co.uk"]',  # The Sun 링크 직접 찾기
                '.yuRUbf a',  # Google 검색 결과 새 포맷
            ]
            
            found_urls = set()
            
            for selector in result_selectors:
                elements = soup.select(selector)
                logger.info(f"Google {selector}: {len(elements)}개 결과")
                
                for element in elements:
                    try:
                        url = element.get('href', '')
                        title = element.get_text(strip=True)
                        
                        # Google 리다이렉트 URL 처리
                        if url.startswith('/url?q='):
                            import urllib.parse
                            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                            if 'q' in parsed:
                                url = parsed['q'][0]
                        
                        # 기본 검증
                        if not url or not title or len(title) < 10:
                            continue
                            
                        # The Sun URL인지 확인
                        if 'thesun.co.uk' not in url:
                            continue
                            
                        # 중복 제거
                        if url in found_urls:
                            continue
                        found_urls.add(url)
                        
                        # 불필요한 링크 필터링
                        skip_patterns = [
                            '/search', '/login', '/register', '/subscribe',
                            '/contact', '/about', '/terms', '/privacy',
                            '/author/', '/tag/', '/feed/', '/sign-up'
                        ]
                        
                        if any(skip in url.lower() for skip in skip_patterns):
                            continue
                        
                        # 부모 요소에서 더 많은 정보 찾기
                        parent = element.parent
                        context = parent.parent if parent and parent.parent else parent if parent else element
                        
                        # 요약 텍스트 찾기 (Google 검색 결과에서)
                        summary = ''
                        if hasattr(context, 'find_all'):
                            summary_elems = context.find_all(['span', 'div'], limit=3)
                            for summary_elem in summary_elems:
                                text = summary_elem.get_text(strip=True)
                                if (len(text) > 30 and len(text) < 300 and 
                                    text != title and 
                                    'google' not in text.lower() and
                                    'search' not in text.lower()):
                                    summary = text
                                    break
                        
                        # 카테고리 추출
                        category = self._extract_thesun_category_from_url(url)
                        
                        # 날짜 (현재 시간 사용)
                        published_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
                        
                        article = {
                            'title': title,
                            'url': url,
                            'summary': summary[:300] if summary else title[:200],
                            'published_date': published_date,
                            'source': 'The Sun',
                            'category': category,
                            'scraped_at': datetime.now().isoformat(),
                            'relevance_score': 1,
                            'image_url': ''
                        }
                        
                        articles.append(article)
                        logger.info(f"Google에서 The Sun 기사 추가: {title[:50]}...")
                        
                        if len(articles) >= limit:
                            break
                            
                    except Exception as e:
                        logger.debug(f"Google 결과 처리 실패: {e}")
                        continue
                
                if len(articles) >= limit:
                    break
                    
        except Exception as e:
            logger.error(f"Google 검색 결과 파싱 실패: {e}")
        
        return articles[:limit] 