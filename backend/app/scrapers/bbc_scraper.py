#!/usr/bin/env python3
# coding: utf-8

import requests
from bs4 import BeautifulSoup
# from typing import List, Dict
import logging
from datetime import datetime, timedelta
import re
import feedparser
try:
    from urllib.parse import urljoin  # Python 3
except ImportError:
    from urlparse import urljoin  # Python 2

logger = logging.getLogger(__name__)

class BBCNewsScraper:
    def __init__(self):
        self.base_url = "https://www.bbc.com"
        self.search_url = "https://www.bbc.com/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        # Real BBC RSS feeds for authentic content
        self.rss_feeds = {
            'world': 'https://feeds.bbci.co.uk/news/world/rss.xml',
            'uk': 'https://feeds.bbci.co.uk/news/uk/rss.xml', 
            'business': 'https://feeds.bbci.co.uk/news/business/rss.xml',
            'technology': 'https://feeds.bbci.co.uk/news/technology/rss.xml',
            'health': 'https://feeds.bbci.co.uk/news/health/rss.xml',
            'science': 'https://feeds.bbci.co.uk/news/science_and_environment/rss.xml',
            'entertainment': 'https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml',
            'sports': 'https://feeds.bbci.co.uk/sport/rss.xml?edition=uk',
            'politics': 'https://feeds.bbci.co.uk/news/politics/rss.xml'
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
            
            logger.debug("BBC 검색 컨테이너 개수: {}".format(len(search_containers)))
            
            found_items = set()  # (title, url) 조합
            found_titles = set()  # 제목만으로도 중복 체크
            found_images = set()  # 이미지 URL 중복 체크
            
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
                    
                    # 이미지 중복 체크 및 처리
                    if image_url:
                        if image_url in found_images:
                            # 중복된 이미지는 사용하지 않음
                            logger.debug("BBC 이미지 중복으로 제외: {}".format(image_url))
                            image_url = ''
                        else:
                            found_images.add(image_url)
                    
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
                        'category': self._extract_category_from_content(title, summary, url),
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
        """BBC 기사에서 고유한 이미지 추출 (로고/placeholder 필터링) - 엄격한 검증"""
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
        
        # 최종 검증: 유효한 이미지 URL이 아니거나 검증 실패시 빈 문자열 반환
        if image_url and not self._is_valid_bbc_image(image_url):
            logger.debug("BBC 이미지 최종 검증 실패: {}".format(image_url))
            return ''
            
        return image_url
    
    def _is_valid_bbc_image(self, url):
        """BBC 이미지 URL이 유효한지 확인 (로고/placeholder 필터링) - 더 엄격한 검증"""
        if not url or len(url.strip()) == 0:
            return False
        
        url_lower = url.lower().strip()
        
        # 기본 필터링 - 제외할 이미지들 (확장된 목록)
        exclude_patterns = [
            'logo', 'placeholder', 'default', 'avatar', 'profile',
            'sprite', 'icon', 'button', 'arrow', 'loading',
            'bbc_logo', 'bbclogo', 'transparent', 'blank.gif',
            'pixel.gif', '1x1', 'spacer', 'promo-sprite', 'thumbnail',
            'favicon', 'apple-touch-icon', 'android-chrome', 'mstile',
            'browserconfig', 'manifest', 'safari-pinned-tab',
            'social-media', 'share-', 'facebook-', 'twitter-',
            'instagram-', 'youtube-', 'linkedin-', 'whatsapp-',
            'embed', 'widget', 'banner', 'ad_', 'ads_', 'advertisement',
            'promo_', 'promotional', 'marketing', 'campaign'
        ]
        
        for pattern in exclude_patterns:
            if pattern in url_lower:
                logger.debug("BBC 이미지 제외 (패턴 매칭): {} in {}".format(pattern, url))
                return False
        
        # 데이터 URL, 빈 이미지, SVG 제외
        if (url.startswith('data:') or 
            url.startswith('//') and len(url) < 10 or
            '.svg' in url_lower):
            logger.debug("BBC 이미지 제외 (형식): {}".format(url))
            return False
        
        # 너무 작은 이미지 크기 제외 (URL에 크기 정보가 있는 경우)
        size_patterns = [
            r'(\d+)x(\d+)', r'w_(\d+)', r'h_(\d+)', 
            r'width[=:](\d+)', r'height[=:](\d+)', r'_(\d+)x(\d+)',
            r'/(\d+)x(\d+)/', r'size=(\d+)'
        ]
        
        import re
        for pattern in size_patterns:
            match = re.search(pattern, url_lower)
            if match:
                try:
                    # 첫 번째 숫자 그룹 가져오기
                    size_groups = match.groups()
                    for group in size_groups:
                        if group and group.isdigit():
                            size = int(group)
                            if size < 200:  # 200px 미만 이미지 제외 (더 엄격하게)
                                logger.debug("BBC 이미지 제외 (크기 작음): {}px in {}".format(size, url))
                                return False
                            break
                except:
                    pass
        
        # 유효한 이미지 확장자나 BBC 이미지 URL 패턴 확인 (더 엄격하게)
        valid_image_extensions = ['.jpg', '.jpeg', '.png', '.webp']
        bbc_image_domains = ['ichef.bbci.co.uk', 'bbc.co.uk', 'bbcimg.co.uk']
        content_keywords = ['image', 'photo', 'picture', 'news', 'article']
        
        # 확장자 확인
        has_valid_extension = any(ext in url_lower for ext in valid_image_extensions)
        
        # BBC 도메인 확인
        has_bbc_domain = any(domain in url_lower for domain in bbc_image_domains)
        
        # 콘텐츠 키워드 확인
        has_content_keyword = any(keyword in url_lower for keyword in content_keywords)
        
        # 최소 조건: 유효한 확장자가 있고 (BBC 도메인이거나 콘텐츠 키워드가 있어야 함)
        is_valid = has_valid_extension and (has_bbc_domain or has_content_keyword)
        
        if not is_valid:
            logger.debug("BBC 이미지 제외 (검증 실패): ext={}, domain={}, content={}, url={}".format(has_valid_extension, has_bbc_domain, has_content_keyword, url))
        
        return is_valid
    
    def _extract_bbc_summary(self, parent_element, article_url):
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
                if not summary and article_url and 'bbc.com' in article_url:
                    summary = self._extract_summary_from_article_page(article_url)
                    
        except Exception as e:
            logger.debug("BBC 본문 추출 실패: {}".format(e))
        
        return summary
    
    def _extract_summary_from_article_page(self, article_url):
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
        if '/sport/' in url or '/sports/' in url:
            return 'sports'
        elif '/business/' in url or '/economy/' in url:
            return 'business'
        elif '/technology/' in url or '/tech/' in url:
            return 'technology'
        elif '/entertainment/' in url or '/celebrity/' in url:
            return 'entertainment'
        elif '/health/' in url or '/medicine/' in url:
            return 'health'
        elif '/world/' in url or '/international/' in url:
            return 'world'
        elif '/news/' in url:
            return 'news'
        else:
            return 'news'
    
    def _extract_category_from_content(self, title, summary, url):
        """제목, 요약, URL을 종합하여 카테고리 추출"""
        # 먼저 URL 기반 분류
        url_category = self._extract_category_from_url(url)
        if url_category != 'news':
            return url_category
        
        # 제목과 요약에서 키워드 기반 분류
        content = (title + ' ' + (summary or '')).lower()
        
        # 기술/AI 키워드 (전각/반각 모두 포함)
        tech_keywords = ['ai', 'ａｉ', 'artificial intelligence', 'technology', 'tech', 'digital', 'cyber', 'computer', 'internet', 'software', 'data', 'algorithm', '인공지능', 'ＡＩ', 'ａｉ', '生成', 'デジタル', 'テクノロジー']
        if any(keyword in content for keyword in tech_keywords):
            return 'technology'
        
        # 스포츠 키워드
        sport_keywords = ['football', 'soccer', 'basketball', 'tennis', 'sports', 'sport', 'game', 'match', 'player', 'team', 'uefa', 'fifa', 'olympics', 'サッカー', 'スポーツ', '축구', '스포츠']
        if any(keyword in content for keyword in sport_keywords):
            return 'sports'
        
        # 비즈니스 키워드
        business_keywords = ['business', 'economy', 'economic', 'finance', 'financial', 'market', 'trade', 'company', 'corporate', 'stock', 'investment', '経済', 'ビジネス', '비즈니스', '경제']
        if any(keyword in content for keyword in business_keywords):
            return 'business'
        
        # 엔터테인먼트 키워드
        entertainment_keywords = ['entertainment', 'celebrity', 'movie', 'film', 'music', 'actor', 'actress', 'singer', 'show', 'television', 'tv', '엔터테인먼트', '연예', '映画', '音楽']
        if any(keyword in content for keyword in entertainment_keywords):
            return 'entertainment'
        
        # 건강 키워드
        health_keywords = ['health', 'medical', 'medicine', 'hospital', 'doctor', 'disease', 'virus', 'covid', 'pandemic', '건강', '의료', '病院', '医療']
        if any(keyword in content for keyword in health_keywords):
            return 'health'
        
        return 'news'
    
    def _extract_category_articles(self, html_content, limit, category):
        """BBC 카테고리 페이지에서 기사 추출 (스포츠, 기술 등)"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            found_items = set()
            found_titles = set()
            found_images = set()  # 이미지 URL 중복 체크
            
            # BBC 카테고리 페이지의 실제 기사 링크 찾기 (개선된 버전)
            article_selectors = [
                # BBC 최신 기사 컨테이너들 (더 구체적으로)
                'div[data-testid="liverpool-card"] a[href*="/news/articles/"]',
                'div[data-testid="london-card"] a[href*="/news/articles/"]', 
                'div[data-testid="manchester-card"] a[href*="/news/articles/"]',
                # 실제 기사 링크들 (articles 포함)
                'a[href*="/news/articles/"]',
                'a[href*="/sport/articles/"]' if category == 'sport' else 'a[href*="/business/articles/"]' if category == 'business' else 'a[href*="/news/articles/"]',
                # 헤드라인 링크들
                'h1 a[href*="/articles/"], h2 a[href*="/articles/"], h3 a[href*="/articles/"]',
                # 메인 헤드라인들 (개선)
                '[data-testid*="headline"] a[href*="/articles/"]',
                '[data-testid*="story"] a[href*="/articles/"]',
                # 기사 카드들 (실제 기사만)
                'article a[href*="/articles/"]',
                'div[class*="card"] a[href*="/articles/"]',
                'div[class*="story"] a[href*="/articles/"]'
            ]
            
            for selector in article_selectors:
                if len(articles) >= limit:
                    break
                    
                try:
                    elements = soup.select(selector)
                    for element in elements:
                        if len(articles) >= limit:
                            break
                            
                        # 링크 추출
                        if element.name == 'a':
                            link_elem = element
                        else:
                            link_elem = element.find('a')
                            
                        if not link_elem:
                            continue
                            
                        href = link_elem.get('href', '')
                        if not href:
                            continue
                            
                        # URL 정규화
                        if href.startswith('/'):
                            url = self.base_url + href
                        elif href.startswith('http'):
                            url = href
                        else:
                            continue
                            
                        # BBC 내부 링크만 허용
                        if 'bbc.com' not in url and 'bbc.co.uk' not in url:
                            continue
                            
                        # 카테고리 관련 URL 필터링 (더 관대하게)
                        category_patterns = {
                            'sport': ['/sport/', '/football/', '/cricket/', '/rugby/', '/tennis/'],
                            'technology': ['/technology/', '/tech/', '/science/'],
                            'business': ['/business/', '/economy/'],
                            'news': ['/news/'],
                            'world': ['/world/', '/international/'],
                            'health': ['/health/', '/medical/']
                        }
                        
                        if category in category_patterns:
                            if not any(pattern in url for pattern in category_patterns[category]):
                                # 카테고리와 맞지 않으면 스킵 (sport 페이지에서는 sport 관련 링크만)
                                continue
                        
                        # 제목 추출
                        title = ''
                        title_elem = link_elem.find(string=True, recursive=True)
                        if title_elem:
                            title = title_elem.strip()
                        else:
                            # 부모 컨테이너에서 제목 찾기
                            parent = link_elem.parent
                            if parent:
                                title_text = parent.get_text(strip=True)
                                if title_text and len(title_text) > 10:
                                    title = title_text[:200]
                        
                        if not title or len(title) < 10:
                            continue
                            
                        # 중복 체크
                        title_normalized = title.lower().strip()
                        if title_normalized in found_titles:
                            continue
                            
                        item_key = (title, url)
                        if item_key in found_items:
                            continue
                            
                        found_items.add(item_key)
                        found_titles.add(title_normalized)
                        
                        # 요약 추출 (간단하게)
                        summary = ''
                        parent_container = link_elem.find_parent(['div', 'article', 'section'])
                        if parent_container:
                            summary_elem = parent_container.find(['p', 'div'], string=lambda x: x and len(x.strip()) > 20)
                            if summary_elem:
                                summary = summary_elem.get_text(strip=True)[:300]
                        
                        # 이미지 추출
                        image_url = self._extract_bbc_image(parent_container if parent_container else link_elem)
                        
                        # 이미지 중복 체크 및 처리
                        if image_url:
                            if image_url in found_images:
                                # 중복된 이미지는 사용하지 않음
                                logger.debug("BBC 카테고리 이미지 중복으로 제외: {}".format(image_url))
                                image_url = ''
                            else:
                                found_images.add(image_url)
                        
                        # 날짜 추출 
                        published_date = self._extract_bbc_date(parent_container if parent_container else link_elem, url)
                        
                        article = {
                            'title': title,
                            'url': url,
                            'summary': summary if summary else title[:200],
                            'published_date': published_date,
                            'source': 'BBC News',
                            'category': self._extract_category_from_content(title, summary, url),
                            'scraped_at': datetime.now().isoformat(),
                            'relevance_score': 1,
                            'image_url': image_url
                        }
                        
                        articles.append(article)
                        
                except Exception as e:
                    logger.debug("BBC 카테고리 파싱 오류 (selector: {}): {}".format(selector, e))
                    continue
                    
        except Exception as e:
            logger.error("BBC 카테고리 페이지 파싱 실패: {}".format(e))
        
        logger.info("BBC {} 카테고리에서 {}개 기사 추출".format(category, len(articles)))
        return articles[:limit]
    
    def get_latest_news(self, category='news', limit=10):
        """BBC RSS feeds를 사용하여 실제 뉴스 가져오기"""
        try:
            logger.info("BBC RSS 기반 뉴스 요청: {}, limit: {}".format(category, limit))
            
            # RSS feeds에서 기사 가져오기 (우선순위)
            rss_articles = self._get_rss_articles(category, limit)
            if rss_articles:
                logger.info("BBC RSS에서 {}개 기사 추출".format(len(rss_articles)))
                return rss_articles
            
            # RSS 실패시 기존 방식 폴백
            logger.info("BBC RSS 실패, 기존 방식으로 폴백")
            if category == 'health':
                return self.search_news('health medical NHS hospital doctor', limit)
            elif category in ['sport', 'sports']:
                return self.search_news('football premier league cricket rugby tennis sport', limit)
            
            # 실제 BBC 카테고리 섹션 URL들 (2025년 기준)
            category_urls = {
                'all': 'https://www.bbc.com',
                'news': 'https://www.bbc.com/news',
                'sports': 'https://www.bbc.com/sport',
                'sport': 'https://www.bbc.com/sport', 
                'business': 'https://www.bbc.com/business',
                'technology': 'https://www.bbc.com/innovation',  # BBC Innovation 섹션
                'tech': 'https://www.bbc.com/innovation',
                'innovation': 'https://www.bbc.com/innovation',
                'entertainment': 'https://www.bbc.com/culture',  # BBC Culture 섹션
                'culture': 'https://www.bbc.com/culture',
                'health': 'https://www.bbc.com/news',  # Health 기사들은 news 섹션에 있음
                'world': 'https://www.bbc.com/news/world',
                'uk': 'https://www.bbc.com/news/uk',
                'politics': 'https://www.bbc.com/news/politics',
                'science': 'https://www.bbc.com/news/science-environment'
            }
            
            url = category_urls.get(category, category_urls['news'])
            print("=== BBC URL 접근: {} ===".format(url))
            logger.error("=== BBC URL 접근 ERROR 로그: {} ===".format(url))
            logger.info("BBC 카테고리 페이지 접근: {}".format(url))
            
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            print("=== BBC 응답 성공: 상태코드 {} ===".format(response.status_code))
            
            # 실제 웹사이트 구조에 맞게 기사 추출
            print("=== BBC _extract_bbc_category_articles 호출 시작 ===")
            articles = self._extract_bbc_category_articles(response.text, limit, category)
            print("=== BBC _extract_bbc_category_articles 결과: {}개 ===".format(len(articles) if articles else 0))
            
            if articles:
                logger.info("BBC {} 카테고리에서 {}개 기사 추출".format(category, len(articles)))
                return articles
            else:
                # 폴백: 검색 사용
                print("=== BBC 폴백 검색 시작 ===")
                logger.info("BBC {} 카테고리 추출 실패, 검색으로 폴백".format(category))
                fallback_keywords = {
                    'sports': 'football premier league',
                    'sport': 'football premier league',
                    'technology': 'technology innovation AI',
                    'tech': 'technology innovation AI',
                    'innovation': 'innovation technology science',
                    'business': 'business economy market',
                    'entertainment': 'entertainment celebrity culture',
                    'culture': 'culture art entertainment',
                    'health': 'health medical NHS',
                    'world': 'world international news',
                    'politics': 'politics government UK',
                    'science': 'science research climate',
                    'news': 'breaking news UK'
                }
                
                keyword = fallback_keywords.get(category, 'breaking news')
                logger.info("BBC 검색 폴백: {} -> {}".format(category, keyword))
                
                return self.search_news(keyword, limit)
            
        except Exception as e:
            print("=== BBC Exception 발생: {} ===".format(e))
            logger.error("BBC 카테고리별 뉴스 가져오기 실패: {}".format(e))
            # 최종 폴백: 검색 사용
            print("=== BBC 최종 폴백 검색 시작 ===")
            return self.search_news('breaking news', limit)
    
    def _extract_bbc_category_articles(self, html_content, limit, category):
        """BBC 카테고리 페이지에서 기사 추출 - 실제 구조 분석 기반 (스포츠 JSON 포함)"""
        articles = []
        
        try:
            logger.info("BBC _extract_bbc_category_articles 호출됨 - category: {}, limit: {}".format(category, limit))
            
            # BBC Sport 페이지는 JSON 구조이므로 별도 처리
            print("=== 카테고리 확인: '{}' in ['sport', 'sports'] = {} ===".format(category, category in ['sport', 'sports']))
            if category in ['sport', 'sports']:
                print("=== BBC Sport JSON 분기 진입 ===")
                logger.info("BBC Sport JSON 구조 파싱 시작")
                sport_articles = self._extract_bbc_sport_json(html_content, limit)
                print("=== BBC Sport JSON 결과: {}개 ===".format(len(sport_articles) if sport_articles else 0))
                if sport_articles:
                    logger.info("BBC Sport JSON에서 {}개 기사 추출".format(len(sport_articles)))
                    return sport_articles
                else:
                    print("=== BBC Sport JSON 파싱 실패, 일반 파싱으로 폴백 ===")
                    logger.info("BBC Sport JSON 파싱 실패, 일반 파싱으로 폴백")
            else:
                print("=== BBC Sport JSON 분기 건너뜀 - 일반 파싱 실행 ===")
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 나머지 카테고리는 기존 로직 사용
            # BBC 실제 기사 선택자들 (헤드라이너 우선)
            article_selectors = [
                # 메인 헤드라이너들 (최우선)
                '[data-testid*="headline"] a[href*="/news/"]',
                '[data-testid*="story"] a[href*="/news/"]',
                '[data-testid*="top-story"] a[href*="/news/"]',
                '.gs-c-promo-heading a[href*="/news/"]',
                '.gel-layout__item a[href*="/news/"]',
                # JSON 데이터에서 추출한 기사들
                'a[href*="/news/articles/"]',
                'a[href*="/sport/articles/"]',
                'a[href*="/business/articles/"]',
                'a[href*="/innovation/articles/"]',
                'a[href*="/culture/articles/"]',
                # 메인 기사 링크들
                'h1 a[href*="/news/"]',
                'h2 a[href*="/news/"]',
                'h3 a[href*="/news/"]',
                'h2 a[href*="/sport/"]',
                'h3 a[href*="/sport/"]',
                # BBC 기사 컨테이너들
                'article a[href*="/news/"]',
                'article a[href*="/sport/"]',
                '.story a[href*="/news/"]',
                '.story a[href*="/sport/"]',
                # BBC 특화 선택자들
                '.media__content a[href*="/news/"]',
                '.media__content a[href*="/sport/"]',
                '.promo-heading a[href*="/news/"]',
                '.promo-heading a[href*="/sport/"]',
                # 일반적인 BBC 링크들
                'a[href*="bbc.com/news/"]',
                'a[href*="bbc.com/sport/"]',
                'a[href*="bbc.com/business/"]',
                'a[href*="bbc.com/innovation/"]',
                'a[href*="bbc.com/culture/"]'
            ]
            
            found_urls = set()
            found_titles = set()
            
            # 1. 먼저 HTML 셀렉터로 실제 링크 추출 (최우선)
            for selector in article_selectors:
                try:
                    links = soup.select(selector)
                    logger.debug("BBC {}: {}개 링크 발견".format(selector, len(links)))
                    
                    for link in links:
                        try:
                            title = link.get_text(strip=True)
                            url = link.get('href', '')
                            
                            # 기본 검증
                            if not title or len(title) < 15:
                                continue
                                
                            if not url:
                                continue
                                
                            # URL 정규화
                            if url.startswith('/'):
                                url = 'https://www.bbc.com' + url
                            elif not url.startswith('http'):
                                url = 'https://www.bbc.com/' + url
                            
                            # BBC URL 확인
                            if 'bbc.com' not in url:
                                continue
                                
                            # 중복 확인 (URL과 제목 모두)
                            if url in found_urls or title.lower() in found_titles:
                                continue
                            found_urls.add(url)
                            found_titles.add(title.lower())
                            if any(skip in url.lower() for skip in [
                                '/search', '/login', '/register', '/iplayer', 
                                '/contact', '/about', '/terms', '/privacy',
                                '/sounds', '/radio', '/tv'
                            ]):
                                continue
                                
                            # 불필요한 제목들 필터링
                            if any(skip in title.lower() for skip in [
                                'follow us', 'subscribe', 'newsletter', 'login',
                                'register', 'contact us', 'privacy policy',
                                'terms of service', 'bbc iplayer', 'bbc sounds'
                            ]):
                                continue
                            
                            # 링크 주변에서 정보 추출
                            parent = link.parent
                            context = parent.parent if parent and parent.parent else parent if parent else link
                            
                            # 요약 추출
                            summary = self._extract_bbc_summary(context, title)
                            
                            # 이미지 추출 (기존 로직 개선 사용)
                            image_url = self._extract_bbc_image_improved(link, url)
                            
                            # 날짜 추출 (개선된 버전)
                            published_date = self._extract_bbc_date_improved(context, url)
                            
                            # 카테고리 추출
                            article_category = self._extract_bbc_category_from_url(url) or category
                            
                            article = {
                                'title': title,
                                'url': url,
                                'summary': summary[:300] if summary else title[:200],
                                'published_date': published_date,
                                'source': 'BBC News',
                                'category': article_category,
                                'scraped_at': datetime.now().isoformat(),
                                'relevance_score': 1,
                                'image_url': image_url
                            }
                            
                            articles.append(article)
                            
                            if len(articles) >= limit:
                                break
                                
                        except Exception as e:
                            logger.debug("BBC 개별 기사 처리 실패: {}".format(e))
                            continue
                    
                    if len(articles) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug("BBC selector {} 처리 실패: {}".format(selector, e))
                    continue
            
            # 3. HTML에서 충분한 기사를 못 찾은 경우 JSON 보조 사용
            if len(articles) < limit:
                json_articles = self._extract_bbc_json_articles(html_content, limit - len(articles))
                for json_article in json_articles:
                    if (json_article['url'] not in found_urls and 
                        json_article['title'].lower() not in found_titles):
                        articles.append(json_article)
                        found_urls.add(json_article['url'])
                        found_titles.add(json_article['title'].lower())
                        
                logger.info("BBC JSON 백업에서 {}개 추가 기사 추출".format(len(json_articles)))
                    
        except Exception as e:
            logger.error("BBC 카테고리 HTML 파싱 실패: {}".format(e))
        
        return articles[:limit]
    
    def _extract_bbc_json_articles(self, html_content, limit):
        """BBC 페이지의 JSON 데이터에서 헤드라이너 기사 추출"""
        articles = []
        
        try:
            import json
            import re
            
            # BBC 페이지에서 JSON 데이터 찾기
            json_patterns = [
                r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                r'<script[^>]*>\s*window\.__INITIAL_STATE__\s*=\s*({.*?});\s*</script>',
                r'"content":\s*(\[.*?\])',
                r'"articles":\s*(\[.*?\])',
                r'"title":\s*"([^"]*Syria[^"]*)"',  # 시리아 관련 헤드라이너
                r'"hre":\s*"([^"]*news/articles/[^"]*)"'
            ]
            
            # JSON 데이터에서 기사 정보 추출
            for pattern in json_patterns:
                matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
                
                for match in matches:
                    try:
                        if isinstance(match, str) and match.strip().startswith('{'):
                            # JSON 객체 파싱
                            data = json.loads(match)
                            articles.extend(self._parse_bbc_json_structure(data, limit))
                        elif isinstance(match, str) and match.strip().startswith('['):
                            # JSON 배열 파싱
                            data = json.loads(match)
                            if isinstance(data, list):
                                for item in data[:limit]:
                                    if isinstance(item, dict) and 'title' in item:
                                        articles.extend(self._parse_bbc_json_item(item))
                        elif 'syria' in match.lower() or 'druze' in match.lower():
                            # 시리아/드루즈 관련 헤드라이너 직접 추출
                            logger.info("BBC 시리아 헤드라이너 발견: {}".format(match))
                            
                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        logger.debug("BBC JSON 파싱 실패: {}".format(e))
                        continue
            
            # 페이지 텍스트에서 다양한 헤드라이너 찾기 (특정 키워드 제한 없이)
            headline_patterns = [
                r'"title":\s*"([^"]{15,120})"',  # JSON에서 제목 추출
                r'<h[1-3][^>]*>([^<]{15,120})</h[1-3]>',  # H1-H3 헤드라인
                r'<title[^>]*>([^<]{15,120})</title>',  # 타이틀 태그
                r'"headline":\s*"([^"]{15,120})"',  # 헤드라인 필드
                r'"summary":\s*"([^"]{15,120})"',  # 요약 필드
            ]
            
            seen_headlines = set()
            for pattern in headline_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                for title in matches:
                    title = title.strip()
                    # 기본 필터링
                    if (len(title) > 15 and len(title) < 120 and 
                        title.lower() not in seen_headlines and
                        not any(skip in title.lower() for skip in [
                            'bbc news', 'follow us', 'subscribe', 'download', 'sign up',
                            'register', 'terms of use', 'privacy', 'cookie', 'accessibility'
                        ])):
                        
                        seen_headlines.add(title.lower())
                        
                        # Skip fake URL generation - use RSS feeds instead
                        continue
                        articles.append(article)
                        logger.info("BBC 헤드라이너 추출: {}".format(title))
                        
                        if len(articles) >= limit:
                            break
                            
                if len(articles) >= limit:
                    break
                        
        except Exception as e:
            logger.debug("BBC JSON 추출 실패: {}".format(e))
        
        return articles[:limit]
    
    def _parse_bbc_json_structure(self, data, limit):
        """BBC JSON 구조에서 기사 정보 파싱"""
        articles = []
        
        try:
            # Next.js 페이지 데이터 구조 탐색
            if 'props' in data and 'pageProps' in data['props']:
                page_data = data['props']['pageProps']
                
                # 페이지 콘텐츠에서 기사 찾기
                if 'data' in page_data and 'content' in page_data['data']:
                    content = page_data['data']['content']
                    
                    for section in content:
                        if isinstance(section, dict) and 'content' in section:
                            section_content = section['content']
                            
                            if isinstance(section_content, list):
                                for item in section_content[:limit]:
                                    if isinstance(item, dict):
                                        article = self._parse_bbc_json_item(item)
                                        if article:
                                            articles.append(article)
                                            
        except Exception as e:
            logger.debug("BBC JSON 구조 파싱 실패: {}".format(e))
        
        return articles
    
    def _parse_bbc_json_item(self, item):
        """BBC JSON 아이템에서 기사 정보 추출"""
        try:
            title = item.get('title', '')
            url = item.get('href', item.get('url', ''))
            description = item.get('description', item.get('summary', ''))
            
            if title and url and len(title) > 10:
                # URL 정규화
                if url.startswith('/'):
                    url = 'https://www.bbc.com' + url
                elif not url.startswith('http'):
                    url = 'https://www.bbc.com/' + url
                
                return {
                    'title': title,
                    'url': url,
                    'summary': description[:300] if description else title[:200],
                    'published_date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),
                    'source': 'BBC News',
                    'category': 'news',
                    'scraped_at': datetime.now().isoformat(),
                    'relevance_score': 1,
                    'image_url': item.get('image', {}).get('src', '') if isinstance(item.get('image'), dict) else ''
                }
                
        except Exception as e:
            logger.debug("BBC JSON 아이템 파싱 실패: {}".format(e))
        
        return None
    
    def _extract_bbc_summary(self, element, title):
        """BBC 기사에서 요약 추출"""
        summary = ''
        
        try:
            if hasattr(element, 'find_all'):
                # BBC 요약 패턴들
                summary_selectors = [
                    'p',
                    '.media__summary',
                    '.promo-text',
                    '.excerpt', 
                    '.summary',
                    '.description'
                ]
                
                for selector in summary_selectors:
                    elements = element.find_all(selector)
                    
                    for elem in elements:
                        text = elem.get_text(strip=True)
                        
                        # 유효한 요약인지 확인
                        if (len(text) > 30 and len(text) < 500 and
                            text != title and
                            not text.startswith('BBC') and
                            not text.startswith('Published') and
                            not text.lower().startswith('click here') and
                            not text.lower().startswith('read more') and
                            'bbc.com' not in text.lower()):
                            
                            summary = text
                            break
                    
                    if summary:
                        break
                        
        except Exception as e:
            logger.debug("BBC 요약 추출 실패: {}".format(e))
        
        return summary
    
    def _extract_bbc_date_improved(self, element, url):
        """BBC 기사에서 날짜 추출 - 개선된 버전"""
        try:
            # 1. 요소에서 날짜 찾기
            if hasattr(element, 'get_text'):
                text = element.get_text()
                
                # BBC 날짜 패턴들
                date_patterns = [
                    r'(\d{1,2}\s+\w+\s+\d{4})',  # 17 July 2025
                    r'(\w+\s+\d{1,2},?\s*\d{4})',  # July 17, 2025
                    r'(\d{1,2}/\d{1,2}/\d{4})',  # 17/07/2025
                    r'(\d{4}-\d{1,2}-\d{1,2})',  # 2025-07-17
                    r'(\d{1,2}\s+hours?\s+ago)',  # 5 hours ago
                    r'(\d{1,2}\s+days?\s+ago)'    # 2 days ago
                ]
                
                for pattern in date_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        try:
                            date_str = match.group(0)
                            
                            if 'hours ago' in date_str.lower():
                                hours = int(re.search(r'\d+', date_str).group())
                                date_obj = datetime.now() - timedelta(hours=hours)
                                return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                            elif 'days ago' in date_str.lower():
                                days = int(re.search(r'\d+', date_str).group())
                                date_obj = datetime.now() - timedelta(days=days)
                                return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                            else:
                                # 일반 날짜 형식들
                                for fmt in ['%d %B %Y', '%B %d, %Y', '%d %b %Y', '%b %d, %Y', '%d/%m/%Y', '%Y-%m-%d']:
                                    try:
                                        date_obj = datetime.strptime(date_str, fmt)
                                        return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                                    except:
                                        continue
                        except:
                            continue
            
            # 2. URL에서 날짜 추출 (BBC URL 패턴)
            # BBC URL 형태: https://www.bbc.com/news/articles/c1234567890
            # 또는 숫자 기반 ID에서 날짜 추출 시도
            url_patterns = [
                r'/(\d{4})/(\d{1,2})/(\d{1,2})/',  # /2025/07/17/
                r'-(\d{4})-(\d{1,2})-(\d{1,2})-',  # -2025-07-17-
            ]
            
            for pattern in url_patterns:
                match = re.search(pattern, url)
                if match:
                    try:
                        year, month, day = match.groups()[:3]
                        date_obj = datetime(int(year), int(month), int(day))
                        return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                    except:
                        continue
                        
        except Exception as e:
            logger.debug("BBC 날짜 추출 실패: {}".format(e))
        
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    def _extract_bbc_category_from_url(self, url):
        """BBC URL에서 카테고리 추출"""
        try:
            if '/sport/' in url:
                return 'sports'
            elif '/business/' in url:
                return 'business'
            elif '/innovation/' in url:
                return 'technology'
            elif '/culture/' in url:
                return 'entertainment'
            elif '/health/' in url:
                return 'health'
            elif '/science-environment/' in url:
                return 'science'
            elif '/politics/' in url:
                return 'politics'
            elif '/world/' in url:
                return 'world'
            elif '/uk/' in url:
                return 'news'
            elif '/news/' in url:
                return 'news'
            else:
                return 'news'
        except:
            return 'news' 

    def _extract_bbc_sport_json(self, html_content, limit):
        """BBC Sport 페이지의 JSON 구조에서 기사 추출"""
        articles = []
        
        try:
            import json
            import re
            
            print("=== BBC Sport JSON 파싱 시작 - HTML 길이: {} ===".format(len(html_content)))
            
            # BBC Sport 페이지에서 실제 스포츠 기사 링크들을 찾는 패턴들
            sport_patterns = [
                # 실제 스포츠 기사 URL 패턴들
                r'href="(/sport/[^"]*articles/[^"]*)"[^>]*>([^<]{20,120})<',
                r'<a[^>]*href="(/sport/[^"]*)"[^>]*>([^<]{20,120})</a>',
                r'"url":\s*"(/sport/[^"]*articles/[^"]*)"[^}]*"title":\s*"([^"]{20,120})"',
                r'"title":\s*"([^"]{20,120})"[^}]*"url":\s*"(/sport/[^"]*articles/[^"]*)"',
                # 일반적인 뉴스 링크 패턴 (스포츠 관련)
                r'<h[1-4][^>]*><a[^>]*href="(/sport/[^"]*)"[^>]*>([^<]{20,120})</a></h[1-4]>',
            ]
            
            found_titles = set()
            found_urls = set()
            
            # 각 패턴으로 기사 추출
            for i, pattern in enumerate(sport_patterns):
                print("=== BBC Sport 패턴 {} 시도 ===".format(i+1))
                matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
                print("=== BBC Sport 패턴 {} 매칭 결과: {}개 ===".format(i+1, len(matches)))
                
                for match in matches:
                    try:
                        # 패턴에 따라 순서가 다를 수 있음
                        if len(match) == 2:
                            if match[0].startswith('/'):
                                url_part, title = match
                            else:
                                title, url_part = match
                        else:
                            continue
                        
                        # URL 정규화
                        if url_part.startswith('/'):
                            url = 'https://www.bbc.com' + url_part
                        else:
                            url = url_part
                        
                        # 기본 검증
                        if not title or len(title.strip()) < 20:
                            continue
                            
                        title = title.strip()
                        
                        # 중복 확인
                        if url in found_urls or title.lower() in found_titles:
                            continue
                            
                        # 무의미한 제목들 필터링
                        if any(skip in title.lower() for skip in [
                            'more', 'view all', 'see all', 'latest', 'follow',
                            'subscribe', 'newsletter', 'homepage', 'menu'
                        ]):
                            continue
                        
                        # 실제 스포츠 관련 키워드 확인
                        sport_keywords = [
                            'football', 'soccer', 'premier league', 'champions league',
                            'cricket', 'rugby', 'tennis', 'golf', 'formula', 'boxing',
                            'olympics', 'world cup', 'uefa', 'fifa', 'player', 'team',
                            'match', 'goal', 'win', 'lose', 'defeat', 'victory'
                        ]
                        
                        has_sport_keyword = any(keyword in title.lower() for keyword in sport_keywords)
                        if not has_sport_keyword:
                            continue
                            
                        found_urls.add(url)
                        found_titles.add(title.lower())
                        
                        article = {
                            'title': title,
                            'url': url,
                            'summary': "BBC Sport: {}".format(title[:150]),
                            'published_date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),
                            'source': 'BBC News',
                            'category': 'sports',
                            'scraped_at': datetime.now().isoformat(),
                            'relevance_score': 1,
                            'image_url': ''
                        }
                        
                        articles.append(article)
                        print("=== BBC Sport 기사 추가: {}... ===".format(title[:50]))
                        
                        if len(articles) >= limit:
                            break
                            
                    except Exception as e:
                        logger.debug("BBC Sport 기사 처리 실패: {}".format(e))
                        continue
                
                if len(articles) >= limit:
                    break
            
            # 충분한 기사를 찾지 못했을 경우 HTML 파싱 시도
            if len(articles) < limit:
                logger.info("BBC Sport JSON에서 {}개만 찾음, HTML 파싱 시도".format(len(articles)))
                html_articles = self._extract_bbc_sport_fallback(html_content, limit - len(articles), found_titles, found_urls)
                articles.extend(html_articles)
                
        except Exception as e:
            logger.error("BBC Sport JSON 파싱 실패: {}".format(e))
        
        return articles
    
    def _extract_bbc_sport_fallback(self, html_content, limit, found_titles, found_urls):
        """BBC Sport 페이지에서 폴백 방식으로 추가 기사 추출"""
        articles = []
        
        try:
            import re
            
            # 더 광범위한 스포츠 기사 패턴들 (하지만 여전히 실제 기사만)
            fallback_patterns = [
                # 실제 기사 URL 패턴들
                r'"text":\s*"([^"]{20,120}[a-z]{3,}[^"]*)".*?"url":\s*"([^"]*sport/[^"]*articles/[^"]*)"',
                r'"label":\s*"([^"]{20,120}[a-z]{3,}[^"]*)".*?"hre":\s*"([^"]*sport/[^"]*articles/[^"]*)"',
                r'"name":\s*"([^"]{20,120}[a-z]{3,}[^"]*)".*?"url":\s*"([^"]*sport/[^"]*articles/[^"]*)"',
                # 더 구체적인 스포츠 기사들
                r'<h[2-4][^>]*>([^<]{20,120})</h[2-4]>.*?href="([^"]*sport/[^"]*articles/[^"]*)"',
                r'"contentTitle":\s*"([^"]{20,120})".*?"url":\s*"([^"]*sport/[^"]*)".*?"type":\s*"article"'
            ]
            
            for pattern in fallback_patterns:
                matches = re.findall(pattern, html_content, re.DOTALL)
                
                for title, url in matches:
                    try:
                        # 기본 검증
                        if not title or len(title) < 20 or not url:
                            continue
                            
                        # URL 정규화
                        if url.startswith('/'):
                            url = 'https://www.bbc.com' + url
                        elif not url.startswith('http'):
                            continue
                            
                        # 중복 제거
                        title_lower = title.lower().strip()
                        if title_lower in found_titles or url in found_urls:
                            continue
                            
                        # 섹션 제목들 필터링
                        if any(section in title_lower for section in [
                            'more', 'explore', 'latest', 'podcast', 'sign up', 'follow',
                            'newsletter', 'subscribe', 'privacy', 'terms', 'contact'
                        ]):
                            continue
                            
                        # 스포츠 관련인지 확인 (더 엄격하게)
                        sport_indicators = [
                            'football', 'soccer', 'premier league', 'champions league',
                            'cricket', 'rugby', 'tennis', 'golf', 'formula', 'boxing',
                            'olympics', 'world cup', 'uefa', 'fifa', 'player', 'team',
                            'match', 'goal', 'win', 'lose', 'defeat', 'victory'
                        ]
                        
                        has_sport_indicator = any(indicator in title_lower for indicator in sport_indicators)
                        if not has_sport_indicator:
                            continue
                            
                        found_titles.add(title_lower)
                        found_urls.add(url)
                        
                        article = {
                            'title': title,
                            'url': url,
                            'summary': "BBC Sport coverage: {}".format(title[:150]),
                            'published_date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),
                            'source': 'BBC Sport',
                            'category': 'sports',
                            'scraped_at': datetime.now().isoformat(),
                            'relevance_score': 1,
                            'image_url': ''
                        }
                        
                        articles.append(article)
                        logger.info("BBC Sport 폴백 기사 추출: {}".format(title))
                        
                        if len(articles) >= limit:
                            break
                            
                    except Exception as e:
                        logger.debug("BBC Sport 폴백 기사 처리 실패: {}".format(e))
                        continue
                        
                if len(articles) >= limit:
                    break
                    
        except Exception as e:
            logger.debug("BBC Sport 폴백 파싱 실패: {}".format(e))
        
        return articles
    
    def _extract_bbc_sport_summary(self, html_content, title, url):
        """BBC Sport 기사의 요약 추출"""
        try:
            import re
            
            # JSON에서 해당 기사의 요약 찾기
            title_escaped = re.escape(title)
            url_escaped = re.escape(url)
            summary_patterns = [
                title_escaped + r'.*?"description":\s*"([^"]+)"',
                title_escaped + r'.*?"summary":\s*"([^"]+)"',
                r'"url":\s*"' + url_escaped + r'".*?"description":\s*"([^"]+)"'
            ]
            
            for pattern in summary_patterns:
                match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
                if match:
                    summary = match.group(1).strip()
                    if summary and len(summary) > 10:
                        return summary
                        
        except Exception as e:
            logger.debug("BBC Sport 요약 추출 실패: {}".format(e))
        
        return "BBC Sport latest update on {}".format(title[:100])
    
    def _extract_bbc_sport_image(self, html_content, url):
        """BBC Sport 기사의 이미지 추출"""
        try:
            import re
            
            # JSON에서 해당 기사의 이미지 찾기
            url_escaped = re.escape(url)
            image_patterns = [
                r'"url":\s*"' + url_escaped + r'".*?"src":\s*"([^"]*ichef\.bbci\.co\.uk[^"]*)"',
                r'"url":\s*"' + url_escaped + r'".*?"image":\s*{[^}]*"src":\s*"([^"]*)"',
                r'"src":\s*"([^"]*ichef\.bbci\.co\.uk[^"]*)"'
            ]
            
            for pattern in image_patterns:
                match = re.search(pattern, html_content, re.DOTALL)
                if match:
                    image_url = match.group(1)
                    if self._is_valid_bbc_image(image_url):
                        if not image_url.startswith('http'):
                            if image_url.startswith('//'):
                                image_url = 'https:' + image_url
                            elif image_url.startswith('/'):
                                image_url = 'https://www.bbc.com' + image_url
                        return image_url
                        
        except Exception as e:
            logger.debug("BBC Sport 이미지 추출 실패: {}".format(e))
        
        return ''
    
    def _get_rss_articles(self, category, limit):
        """BBC RSS feeds에서 실제 기사 추출"""
        articles = []
        
        try:
            # 카테고리에 따라 RSS feed 선택
            feed_urls = []
            
            if category in ['news', 'all']:
                feed_urls = [self.rss_feeds['world'], self.rss_feeds['uk']]
            elif category in ['sport', 'sports']:
                feed_urls = [self.rss_feeds['sports']]
            elif category == 'business':
                feed_urls = [self.rss_feeds['business']]
            elif category in ['technology', 'tech']:
                feed_urls = [self.rss_feeds['technology']]
            elif category == 'health':
                feed_urls = [self.rss_feeds['health']]
            elif category == 'science':
                feed_urls = [self.rss_feeds['science']]
            elif category == 'entertainment':
                feed_urls = [self.rss_feeds['entertainment']]
            elif category == 'politics':
                feed_urls = [self.rss_feeds['politics']]
            else:
                feed_urls = [self.rss_feeds['world'], self.rss_feeds['uk']]
            
            seen_urls = set()
            
            for feed_url in feed_urls:
                try:
                    logger.info("BBC RSS feed 액세스: {}".format(feed_url))
                    feed = feedparser.parse(feed_url)
                    
                    if feed.entries:
                        logger.info("BBC RSS에서 {}개 엔트리 발견".format(len(feed.entries)))
                        
                        for entry in feed.entries:
                            if len(articles) >= limit:
                                break
                                
                            try:
                                # RSS 엔트리에서 데이터 추출
                                title = entry.title.strip() if hasattr(entry, 'title') else ''
                                url = entry.link.strip() if hasattr(entry, 'link') else ''
                                summary = self._extract_rss_summary(entry)
                                published_date = self._extract_rss_date(entry)
                                image_url = self._extract_rss_image(entry)
                                
                                # 기본 검증
                                if not title or len(title) < 10 or not url:
                                    continue
                                    
                                # URL 검증 및 중복 방지
                                if not self._is_valid_bbc_url(url) or url in seen_urls:
                                    continue
                                    
                                seen_urls.add(url)
                                
                                # 카테고리 추출
                                article_category = self._extract_category_from_content(title, summary, url)
                                
                                article = {
                                    'title': title,
                                    'url': url,
                                    'summary': summary[:300] if summary else title[:200],
                                    'published_date': published_date,
                                    'source': 'BBC News',
                                    'category': article_category,
                                    'scraped_at': datetime.now().isoformat(),
                                    'relevance_score': 1,
                                    'image_url': image_url
                                }
                                
                                articles.append(article)
                                logger.info("BBC RSS 기사 추가: {}".format(title))
                                
                            except Exception as e:
                                logger.debug("BBC RSS 엔트리 처리 실패: {}".format(e))
                                continue
                    else:
                        logger.warning("BBC RSS feed 비어있음: {}".format(feed_url))
                        
                except Exception as e:
                    logger.error("BBC RSS feed 액세스 실패 {}: {}".format(feed_url, e))
                    continue
                    
                if len(articles) >= limit:
                    break
                    
        except Exception as e:
            logger.error("BBC RSS 처리 실패: {}".format(e))
            
        return articles[:limit]
    
    def _extract_rss_summary(self, entry):
        """RSS 엔트리에서 요약 추출"""
        try:
            # RSS 요약 필드들 확인
            if hasattr(entry, 'summary') and entry.summary:
                summary = BeautifulSoup(entry.summary, 'html.parser').get_text(strip=True)
                if len(summary) > 20:
                    return summary
                    
            if hasattr(entry, 'description') and entry.description:
                description = BeautifulSoup(entry.description, 'html.parser').get_text(strip=True)
                if len(description) > 20:
                    return description
                    
            # content 필드 확인
            if hasattr(entry, 'content') and entry.content:
                for content in entry.content:
                    if hasattr(content, 'value'):
                        content_text = BeautifulSoup(content.value, 'html.parser').get_text(strip=True)
                        if len(content_text) > 20:
                            return content_text[:300]
                            
        except Exception as e:
            logger.debug("BBC RSS 요약 추출 실패: {}".format(e))
            
        return ''
    
    def _extract_rss_date(self, entry):
        """RSS 엔트리에서 날짜 추출"""
        try:
            # published 날짜 확인
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                date_obj = datetime(*entry.published_parsed[:6])
                return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                
            if hasattr(entry, 'published') and entry.published:
                # RFC 2822 형식으로 파싱 시도
                try:
                    from email.utils import parsedate_tz
                    parsed = parsedate_tz(entry.published)
                    if parsed:
                        date_obj = datetime(*parsed[:6])
                        return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                except:
                    pass
                    
            # updated 날짜 확인
            if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                date_obj = datetime(*entry.updated_parsed[:6])
                return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                
        except Exception as e:
            logger.debug("BBC RSS 날짜 추출 실패: {}".format(e))
            
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    def _extract_rss_image(self, entry):
        """RSS 엔트리에서 이미지 URL 추출"""
        try:
            # enclosures에서 이미지 찾기
            if hasattr(entry, 'enclosures'):
                for enclosure in entry.enclosures:
                    if hasattr(enclosure, 'type') and enclosure.type and 'image' in enclosure.type:
                        if hasattr(enclosure, 'href') and self._is_valid_bbc_image(enclosure.href):
                            return enclosure.href
                            
            # media_thumbnail 확인
            if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                for thumbnail in entry.media_thumbnail:
                    if isinstance(thumbnail, dict) and 'url' in thumbnail:
                        if self._is_valid_bbc_image(thumbnail['url']):
                            return thumbnail['url']
                            
            # media_content 확인
            if hasattr(entry, 'media_content') and entry.media_content:
                for media in entry.media_content:
                    if isinstance(media, dict) and 'url' in media:
                        if media.get('type', '').startswith('image/'):
                            if self._is_valid_bbc_image(media['url']):
                                return media['url']
                                
            # RSS 내용에서 이미지 태그 찾기
            content_fields = []
            if hasattr(entry, 'summary'):
                content_fields.append(entry.summary)
            if hasattr(entry, 'content'):
                for content in entry.content:
                    if hasattr(content, 'value'):
                        content_fields.append(content.value)
                        
            for content in content_fields:
                try:
                    soup = BeautifulSoup(content, 'html.parser')
                    img_tags = soup.find_all('img')
                    for img in img_tags:
                        src = img.get('src', '')
                        if src and self._is_valid_bbc_image(src):
                            # 상대 URL을 절대 URL로 변환
                            if src.startswith('//'):
                                return 'https:' + src
                            elif src.startswith('/'):
                                return 'https://www.bbc.com' + src
                            elif src.startswith('http'):
                                return src
                except:
                    continue
                    
        except Exception as e:
            logger.debug("BBC RSS 이미지 추출 실패: {}".format(e))
            
        return ''
    
    def _is_valid_bbc_url(self, url):
        """BBC URL이 유효한지 검증"""
        try:
            if not url or 'bbc.com' not in url.lower():
                return False
                
            # 제외할 URL 패턴들
            exclude_patterns = [
                '/search', '/contact', '/help', '/about', '/terms',
                '/privacy', '/cookies', '/accessibility', '/iplayer', 
                '/sounds', '/weather', '/sport/live', '/news/live'
            ]
            
            for pattern in exclude_patterns:
                if pattern in url.lower():
                    return False
                    
            # 실제 기사 URL 패턴 확인
            valid_patterns = [
                '/news/', '/sport/', '/business/', '/technology/',
                '/innovation/', '/culture/', '/health/', '/science-environment/'
            ]
            
            return any(pattern in url.lower() for pattern in valid_patterns)
            
        except Exception as e:
            logger.debug("BBC URL 검증 실패: {}".format(e))
            return False 