#!/usr/bin/env python3
# coding: utf-8

import requests
from bs4 import BeautifulSoup
from typing import List, Dict
import logging
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)

class BBCNewsScraper:
    def __init__(self):
        self.base_url = "https://www.bbc.com"
        self.search_url = "https://www.bbc.com/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
    def search_news(self, query, limit=10):
        try:
            logger.info("BBC search: {}".format(query))
            
            params = {'q': query}
            response = requests.get(self.search_url, params=params, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            articles = self._extract_search_results(response.text, limit)
            
            logger.info("BBC found {} search results".format(len(articles)))
            return articles
            
        except Exception as e:
            logger.error("BBC search failed: {}".format(e))
            return []
    
    def _extract_search_results(self, html_content, limit):
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # BBC 검색 결과 컨테이너 찾기 (제목+요약문 동시 포함 방법 - 더 안정적)
            search_containers = []
            for div in soup.find_all('div'):
                # 제목 링크 확인
                has_title_link = div.find('a', href=lambda x: x and ('/news/' in x or '/sport/' in x or '/audio/' in x or '/video' in x))
                # 요약문 확인
                has_summary = div.find('div', class_=lambda x: x and 'sc-cdecfb63-3' in str(x))
                
                if has_title_link and has_summary:
                    search_containers.append(div)
            
            logger.debug(f"BBC 검색 컨테이너 개수: {len(search_containers)}")
            
            found_items = set()  # (title, url) 조합
            found_titles = set()  # 제목만으로도 중복 체크
            
            for container in search_containers:
                if len(articles) >= limit:
                    break
                    
                try:
                    # 컨테이너 내에서 제목과 링크 찾기
                    title_links = container.find_all('a', href=True)
                    title_element = None
                    url = None
                    title = None
                    
                    for link in title_links:
                        href = link.get('href', '')
                        if href and ('/news/' in href or '/sport/' in href or '/audio/' in href or '/video' in href):
                            # URL 정규화
                            if href.startswith('/'):
                                url = self.base_url + href
                            else:
                                url = href
                            
                            title = link.get_text(strip=True)
                            title_element = link
                            break
                    
                    if not title or not url or len(title) < 10:
                        continue
                        
                    # 컨테이너 내에서 요약문 찾기 (직접 매칭)
                    summary = ''
                    summary_elements = container.find_all('div', class_=lambda x: x and 'sc-cdecfb63-3' in str(x))
                    
                    for summary_elem in summary_elements:
                        summary_text = summary_elem.get_text(strip=True)
                        if (summary_text and len(summary_text) > 20 and 
                            summary_text != title and
                            not summary_text.startswith('Copyright') and
                            'BBC' not in summary_text):
                            summary = summary_text
                            break
                    
                    # 이미지 추출
                    image_url = self._extract_bbc_image(container)
                    
                    # 의미없는 제목 필터링
                    if (title.lower().strip() in ['news', 'sport', 'politics', 'business', 'technology',
                                                 'entertainment', 'health', 'science', 'education', 'uk', 'world',
                                                 'breaking news', 'latest news'] or 
                        summary.startswith('Copyright') and 'BBC' in summary and len(summary) < 200):
                        continue
                    
                    if 'bbc.com' not in url:
                        continue
                    
                    # 카테고리/토픽 페이지 제외 (실제 기사가 아닌 경우)
                    exclude_patterns = [
                        '/topics/', '/news/uk$', '/news/politics$', '/news/england$',
                        '/news/scotland$', '/news/wales$', '/news/northern_ireland$',
                        '/news/world$', '/news/business$', '/news/technology$',
                        '/news/entertainment$', '/news/health$', '/news/science$',
                        '/news/us-canada$', '/news/europe$', '/news/asia$',
                        '/news/africa$', '/news/australia$', '/news/latin_america$',
                        '/news/war-in-ukraine', '/sport$', '/news/coronavirus$',
                        '/news/disability$', '/news/education$', '/news/special_reports$'
                    ]
                    
                    if any(pattern in url for pattern in exclude_patterns):
                        continue
                    
                    # 실제 기사 URL인지 확인 (ID나 날짜 포함 여부)
                    import re
                    # 실제 기사는 보통 숫자가 포함된 긴 URL을 가짐
                    has_article_pattern = bool(re.search(r'/articles/|/videos/|/\d{4}/\d{2}/\d{2}/|\w{8,}', url))
                    
                    # 카테고리 페이지가 아닌 실제 기사만 허용 (더 강화된 필터링)
                    category_page_patterns = [
                        '/news/uk$', '/news/us-canada$', '/news/world$', '/news/business$',
                        '/news/politics$', '/news/technology$', '/news/entertainment$', 
                        '/news/health$', '/news/science$', '/news/education$',
                        '/news/england$', '/news/scotland$', '/news/wales$', 
                        '/news/northern_ireland$', '/sport$', '/news/coronavirus$',
                        '/news/disability$', '/news/special_reports$'
                    ]
                    
                    is_category_page = any(re.search(pattern, url) for pattern in category_page_patterns)
                    
                    if is_category_page or (not has_article_pattern and len(url.split('/')) <= 5):
                        continue
                    
                    # 이미지 URL 정규화
                    if image_url and not image_url.startswith('http'):
                        if image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        elif image_url.startswith('/'):
                            image_url = self.base_url + image_url
                    
                    # 제목 중복 체크 (더 강화된 중복 제거)
                    title_normalized = title.lower().strip()
                    if title_normalized in found_titles:
                        continue
                    
                    item_key = (title, url)
                    if item_key in found_items:
                        continue
                    
                    found_items.add(item_key)
                    found_titles.add(title_normalized)
                    
                    # BBC 날짜 추출
                    published_date = self._extract_bbc_date(container, url)
                    
                    article = {
                        'title': title,
                        'url': url,
                        'summary': summary[:300] if summary else '',
                        'published_date': published_date,
                        'source': 'BBC News',
                        'category': self._extract_category_from_url(url),
                        'scraped_at': datetime.now().isoformat(),
                        'relevance_score': 1,
                        'image_url': image_url
                    }
                    
                    articles.append(article)
                    
                except Exception as e:
                    logger.debug("BBC container parsing failed: {}".format(e))
                    continue
                
                if len(articles) >= limit:
                    break
                    
        except Exception as e:
            logger.error("BBC HTML parsing failed: {}".format(e))
        
        return articles[:limit]
    
    def _extract_bbc_image(self, element):
        """BBC 기사에서 고유한 이미지 추출 (로고/placeholder 필터링)"""
        image_url = ''
        
        try:
            # 1. 요소 자체에서 이미지 찾기
            if element.name == 'img':
                img_elem = element
            else:
                # 2. 자식 요소에서 이미지 찾기
                img_elem = element.find('img')
            
            if img_elem:
                # 다양한 속성에서 이미지 URL 시도
                for attr in ['src', 'data-src', 'data-lazy-src', 'srcset', 'data-srcset']:
                    img_src = img_elem.get(attr, '')
                    if img_src:
                        # srcset의 경우 첫 번째 URL만 사용
                        if attr in ['srcset', 'data-srcset']:
                            img_src = img_src.split(',')[0].split(' ')[0]
                        
                        if self._is_valid_bbc_image(img_src):
                            image_url = img_src
                            break
            
            # 3. 부모/형제 요소에서 이미지 찾기
            if not image_url:
                # 부모 컨테이너에서 이미지 찾기
                for parent_level in range(3):  # 최대 3단계 위까지 찾기
                    parent = element.find_parent()
                    for _ in range(parent_level):
                        if parent:
                            parent = parent.find_parent()
                    
                    if parent:
                        img_elems = parent.find_all('img')
                        for img_elem in img_elems:
                            for attr in ['src', 'data-src', 'data-lazy-src', 'srcset']:
                                img_src = img_elem.get(attr, '')
                                if img_src:
                                    if attr in ['srcset']:
                                        img_src = img_src.split(',')[0].split(' ')[0]
                                    
                                    if self._is_valid_bbc_image(img_src):
                                        image_url = img_src
                                        break
                            if image_url:
                                break
                    if image_url:
                        break
            
            # 4. 형제 요소에서 이미지 찾기
            if not image_url:
                siblings = [element.find_previous_sibling(), element.find_next_sibling()]
                for sibling in siblings:
                    if sibling and hasattr(sibling, 'find'):
                        img_elem = sibling.find('img')
                        if img_elem:
                            for attr in ['src', 'data-src', 'data-lazy-src']:
                                img_src = img_elem.get(attr, '')
                                if img_src and self._is_valid_bbc_image(img_src):
                                    image_url = img_src
                                    break
                        if image_url:
                            break
                            
        except Exception as e:
            logger.debug("BBC 이미지 추출 실패: {}".format(e))
        
        return image_url
    
    def _is_valid_bbc_image(self, url):
        """BBC 이미지 URL이 유효한지 확인 (로고/placeholder 필터링)"""
        if not url:
            return False
        
        url_lower = url.lower()
        
        # 기본 필터링 - 제외할 이미지들
        exclude_patterns = [
            'logo', 'placeholder', 'default', 'avatar', 'profile',
            'sprite', 'icon', 'button', 'arrow', 'loading',
            'bbc_logo', 'bbclogo', 'transparent', 'blank.gif',
            'pixel.gif', '1x1', 'spacer', 'promo-sprite'
        ]
        
        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False
        
        # 데이터 URL 제외
        if url.startswith('data:'):
            return False
        
        # 너무 작은 이미지 크기 제외 (URL에 크기 정보가 있는 경우)
        size_patterns = [
            r'(\d+)x(\d+)', r'w_(\d+)', r'h_(\d+)', 
            r'width[=:](\d+)', r'height[=:](\d+)'
        ]
        
        import re
        for pattern in size_patterns:
            match = re.search(pattern, url_lower)
            if match:
                try:
                    size = int(match.group(1))
                    if size < 100:  # 100px 미만 이미지 제외
                        return False
                except:
                    pass
        
        # 유효한 이미지 확장자나 BBC 이미지 URL 패턴 확인
        valid_patterns = [
            '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp',
            'ichef.bbci.co.uk', 'bbc.co.uk', 'bbcimg.co.uk',
            'image', 'photo', 'picture'
        ]
        
        return any(pattern in url_lower for pattern in valid_patterns)
    
    def _extract_bbc_summary(self, parent_element, article_url: str) -> str:
        """BBC 기사에서 본문 요약 추출 (강화된 버전)"""
        summary = ''
        
        try:
            # 1. 먼저 검색 결과 페이지에서 본문 찾기 (더 효율적)
            if not summary:
                # 1. BBC 검색 결과 페이지 특화 셀렉터들 (정확한 선택자)
                bbc_summary_selectors = [
                    '.sc-cdecfb63-3.pGVVH',  # BBC 검색 결과 본문 정확한 클래스
                    '.sc-cdecfb63-3',  # BBC 검색 결과 본문 클래스 (단일)
                    '[class*="sc-cdecfb63-3"]',  # BBC 검색 결과 본문 클래스 (부분매치)
                    '[class*="pGVVH"]',  # BBC 검색 결과 본문 클래스 (보조)
                    'p',  # 기본 문단
                    '.summary', '.excerpt', '.description', '.intro',
                    '[class*="summary"]', '[class*="excerpt"]', '[class*="description"]',
                    '.story-body p', '.article-body p'
                ]
                
                # 부모 요소와 그 주변에서 찾기
                search_elements = []
                if hasattr(parent_element, 'find_parent'):
                    # 현재 부모
                    search_elements.append(parent_element)
                    # 부모의 부모 (더 넓은 컨테이너)
                    grandparent = parent_element.find_parent()
                    if grandparent:
                        search_elements.append(grandparent)
                        # 부모의 부모의 부모 (최상위 검색 결과 컨테이너)
                        great_grandparent = grandparent.find_parent()
                        if great_grandparent:
                            search_elements.append(great_grandparent)
                
                for search_elem in search_elements:
                    if not hasattr(search_elem, 'find'):
                        continue
                        
                    for selector in bbc_summary_selectors:
                        desc_elem = search_elem.find(selector)
                        if desc_elem:
                            text = desc_elem.get_text(strip=True)
                            if (text and len(text) > 20 and 
                                not text.startswith('Copyright') and
                                'BBC' not in text and
                                text != parent_element.get_text(strip=True) if hasattr(parent_element, 'get_text') else True):
                                summary = text
                                break
                    if summary:
                        break
                
                # 2. 형제 요소들에서 본문 찾기
                if not summary and hasattr(parent_element, 'find_next_sibling'):
                    siblings = [parent_element.find_next_sibling(), parent_element.find_previous_sibling()]
                    for sibling in siblings:
                        if sibling and hasattr(sibling, 'find'):
                            for selector in bbc_summary_selectors:
                                desc_elem = sibling.find(selector)
                                if desc_elem:
                                    text = desc_elem.get_text(strip=True)
                                    if text and len(text) > 20 and not text.startswith('Copyright'):
                                        summary = text
                                        break
                            if summary:
                                break
                
            # 3. 검색 결과에서 찾지 못한 경우에만 기사 페이지로 이동
            if not summary and article_url and 'bbc.com' in article_url:
                summary = self._extract_summary_from_article_page(article_url)
                
        except Exception as e:
            logger.debug("BBC 본문 추출 실패: {}".format(e))
        
        return summary
    
    def _extract_summary_from_article_page(self, article_url: str) -> str:
        """실제 BBC 기사 페이지에서 본문 추출"""
        try:
            response = requests.get(article_url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # BBC 기사 페이지의 본문 찾기
                selectors = [
                    'meta[property="og:description"]',
                    'meta[name="description"]',
                    '.story-body p',
                    '.article-body p',
                    '[data-component="text-block"] p',
                    '.ssrcss-uf6wea-RichTextComponentWrapper p',
                    '.gel-body-copy',
                    '.story-intro',
                    '.article-intro'
                ]
                
                for selector in selectors:
                    elem = soup.select_one(selector)
                    if elem:
                        text = elem.get('content') or elem.get_text(strip=True)
                        if text and len(text) > 20 and not text.startswith('Copyright'):
                            return text[:300]  # 300자로 제한
                            
                # 여러 p 태그 조합해서 본문 만들기
                paragraphs = soup.select('.story-body p, .article-body p, [data-component="text-block"] p')
                if paragraphs:
                    combined_text = ' '.join([p.get_text(strip=True) for p in paragraphs[:2]])  # 첫 2개 문단
                    if combined_text and len(combined_text) > 20:
                        return combined_text[:300]
                        
        except Exception as e:
            logger.debug("BBC 기사 페이지에서 본문 추출 실패: {}".format(e))
        
        return ''

    def _extract_bbc_date(self, element, url):
        """BBC 기사에서 날짜 추출"""
        try:
            # 1. 요소에서 날짜 정보 찾기
            text = element.get_text()
            
            # BBC 날짜 패턴들
            date_patterns = [
                r'(\d{1,2}\s+hours?\s+ago)',  # "2 hours ago"
                r'(\d{1,2}\s+days?\s+ago)',   # "3 days ago"
                r'(\d{1,2}\s+minutes?\s+ago)', # "30 minutes ago"
                r'(\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})',  # "15 Jul 2024"
                r'((January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})',  # "July 15, 2024"
                r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})',  # "15/07/2024"
                r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',  # "2024/07/15"
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
                        
                        # "X minutes ago" 형태 처리
                        elif 'minutes ago' in date_str.lower():
                            minutes = int(re.search(r'\d+', date_str).group())
                            date_obj = datetime.now() - timedelta(minutes=minutes)
                            return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                        
                        # 일반 날짜 파싱
                        date_formats = [
                            '%d %b %Y', '%d %B %Y', '%B %d, %Y', '%b %d, %Y',
                            '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%Y-%m-%d'
                        ]
                        
                        for fmt in date_formats:
                            try:
                                date_obj = datetime.strptime(date_str, fmt)
                                return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                            except:
                                continue
                    except:
                        continue
            
            # 2. 부모/형제 요소에서 날짜 찾기
            for parent_level in range(3):
                parent = element.find_parent()
                for _ in range(parent_level):
                    if parent:
                        parent = parent.find_parent()
                
                if parent:
                    # time 태그나 날짜 관련 클래스 찾기
                    time_elem = parent.find('time')
                    if time_elem:
                        datetime_attr = time_elem.get('datetime')
                        if datetime_attr:
                            try:
                                # ISO format 처리
                                if 'T' in datetime_attr:
                                    date_obj = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                                else:
                                    date_obj = datetime.fromisoformat(datetime_attr)
                                return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                            except:
                                pass
                        
                        # time 태그의 텍스트에서 날짜 추출
                        time_text = time_elem.get_text(strip=True)
                        if time_text:
                            for pattern in date_patterns:
                                match = re.search(pattern, time_text, re.IGNORECASE)
                                if match:
                                    # 위와 동일한 처리 로직
                                    pass
            
            # 3. URL에서 날짜 추출
            url_date_match = re.search(r'/(\d{4})/(\d{1,2})/(\d{1,2})/', url)
            if url_date_match:
                year, month, day = url_date_match.groups()
                date_obj = datetime(int(year), int(month), int(day))
                return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
            
        except Exception as e:
            logger.debug("BBC 날짜 추출 실패: {}".format(e))
        
        # 기본값: 현재 시간 (최신 뉴스라고 가정)
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')

    def _extract_category_from_url(self, url):
        if '/sport/' in url:
            return 'sport'
        elif '/news/' in url:
            return 'news'
        else:
            return 'news'
    
    def get_latest_news(self, category='news', limit=10):
        category_keywords = {
            'news': 'breaking news',
            'sport': 'football',
            'business': 'business'
        }
        
        keyword = category_keywords.get(category, 'news')
        return self.search_news(keyword, limit) 