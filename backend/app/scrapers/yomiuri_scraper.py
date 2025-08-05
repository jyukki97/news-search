# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime, timedelta
import json
import re
import time
import feedparser  # Added for RSS parsing
from urllib.parse import quote

logger = logging.getLogger(__name__)

class YomiuriScraper:
    """Yomiuri Shimbun 뉴스 스크래퍼 (www.yomiuri.co.jp)"""
    
    def __init__(self):
        self.base_url = "https://www.yomiuri.co.jp"
        self.search_url = "https://www.yomiuri.co.jp/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        # RSS feeds have been discontinued by Yomiuri (all return 404)
        # Keeping structure for compatibility but RSS is disabled
        self.rss_feeds_disabled = {
            # These RSS feeds no longer exist (404 errors)
            'national': 'https://www.yomiuri.co.jp/national/rss.xml',
            'economy': 'https://www.yomiuri.co.jp/economy/rss.xml',
            'sports': 'https://www.yomiuri.co.jp/sports/rss.xml',
            'world': 'https://www.yomiuri.co.jp/world/rss.xml',
            'politics': 'https://www.yomiuri.co.jp/politics/rss.xml',
            'culture': 'https://www.yomiuri.co.jp/culture/rss.xml',
            'science': 'https://www.yomiuri.co.jp/science/rss.xml',
            'trending': 'https://www.yomiuri.co.jp/national/rss.xml',
            'latest': 'https://www.yomiuri.co.jp/national/rss.xml'
        }
        
        # Enhanced section URLs for better article collection
        self.enhanced_section_urls = [
            'https://www.yomiuri.co.jp/national/',
            'https://www.yomiuri.co.jp/politics/',
            'https://www.yomiuri.co.jp/economy/',
            'https://www.yomiuri.co.jp/world/',
            'https://www.yomiuri.co.jp/sports/',
            'https://www.yomiuri.co.jp/culture/',
            'https://www.yomiuri.co.jp/science/',
            'https://www.yomiuri.co.jp/local/',  # Add local news
            'https://www.yomiuri.co.jp/editorial/', # Add editorials
            'https://www.yomiuri.co.jp/life/',  # Add lifestyle
        ]
        
    def search_news(self, query, limit=10):
        """Yomiuri Shimbun에서 뉴스 검색"""
        try:
            logger.info("Yomiuri Shimbun 검색: {}".format(query))
            
            # 실제 Yomiuri 검색 API URL 사용
            search_url = "https://www.yomiuri.co.jp/web-search/?st=1&wo={}&ac=srch&ar=1&fy=&fm=&fd=&ty=&tm=&td=".format(quote(query))
            
            logger.info("Yomiuri 검색 시도: {}".format(search_url))
            response = requests.get(search_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            articles = self._extract_search_results(response.text, limit, query)
            if articles:
                logger.info("Yomiuri에서 {}개 기사 발견".format(len(articles)))
                return articles
            else:
                logger.debug("Yomiuri 검색 결과 없음")
                
                # 검색 실패 시 영어 섹션 최신 뉴스로 대체
                logger.info("Yomiuri 검색 실패, 최신 뉴스로 대체")
                return self.get_latest_news('news', limit)
            
        except Exception as e:
            logger.error("Yomiuri 검색 실패: {}".format(e))
            # 오류 시에도 최신 뉴스로 폴백
            return self.get_latest_news('news', limit)
    
    def _extract_search_results(self, html_content, limit, query=''):
        """HTML에서 검색 결과 추출"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Yomiuri 기사 구조 찾기
            article_selectors = [
                'article',
                '.article',
                '.news-item',
                '.story',
                '.post',
                '.list-item',
                '.news-list-item',
                '[class*="article"]',
                '[class*="news"]',
                '[class*="story"]',
                '[class*="list"]',
                '[class*="item"]'
            ]
            
            found_items = set()
            
            for selector in article_selectors:
                elements = soup.select(selector)
                if not elements:
                    continue
                    
                logger.debug("Yomiuri {}: {}개 요소 발견".format(selector, len(elements)))
                
                for element in elements:
                    try:
                        # 제목 찾기
                        title = ''
                        title_selectors = ['h1', 'h2', 'h3', 'h4', '.title', '.headline', '.news-title', 'a']
                        
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
                        
                        if not url or 'yomiuri.co.jp' not in url:
                            continue
                        
                        # 중복 확인
                        if url in found_items:
                            continue
                        found_items.add(url)
                        
                        # 요약 찾기
                        summary = ''
                        summary_selectors = ['p', '.excerpt', '.summary', '.description', '.lead', '.intro', '.news-summary']
                        
                        for sum_sel in summary_selectors:
                            sum_elem = element.find(sum_sel)
                            if sum_elem:
                                sum_text = sum_elem.get_text(strip=True)
                                if len(sum_text) > 30 and not sum_text.startswith('Yomiuri'):  # 최소 요약 길이
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
                        category = self._extract_category_from_content(title, summary, url)
                        
                        article = {
                            'title': title,
                            'url': url,
                            'summary': summary[:300] if summary else title[:200],
                            'published_date': published_date,
                            'source': 'Yomiuri Shimbun',
                            'category': category,
                            'scraped_at': datetime.now().isoformat(),
                            'relevance_score': 1,
                            'image_url': image_url
                        }
                        
                        articles.append(article)
                        
                        if len(articles) >= limit:
                            break
                            
                    except Exception as e:
                        logger.debug("Yomiuri 기사 파싱 실패: {}".format(e))
                        continue
                
                if len(articles) >= limit:
                    break
                    
        except Exception as e:
            logger.error("Yomiuri HTML 파싱 실패: {}".format(e))
        
        return articles[:limit]
    
    def _extract_date(self, element, url):
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
                r'(\d{4}年\d{1,2}月\d{1,2}日)',  # 일본 한자 날짜 형식
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
                        
                        # 일본 한자 날짜 형식 처리
                        elif '年' in date_str and '月' in date_str and '日' in date_str:
                            # 2024年7月15日 형태를 2024/7/15로 변환
                            date_clean = re.sub(r'(\d{4})年(\d{1,2})月(\d{1,2})日', r'\1/\2/\3', date_str)
                            try:
                                date_obj = datetime.strptime(date_clean, '%Y/%m/%d')
                                return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                            except:
                                pass
                        
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
            logger.debug("Yomiuri 날짜 추출 실패: {}".format(e))
        
        # 기본값: 현재 시간
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    def _extract_category_from_url(self, url):
        """URL에서 카테고리 추출"""
        try:
            # Yomiuri URL 패턴에서 카테고리 추출
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

            else:
                return 'news'
        except:
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
    
    def get_latest_news(self, category='news', limit=10):
        """Enhanced Yomiuri news retrieval with multi-method approach"""
        try:
            logger.info("Yomiuri 뉴스 요청: {}, limit: {}".format(category, limit))
            all_articles = []
            
            # Multi-method approach for 'all', 'trending', 'popular' categories
            if category in ['all', 'trending', 'popular']:
                logger.info("Yomiuri multi-source approach")
                
                # Method 1: Homepage first (most important articles)
                homepage_articles = self._get_enhanced_homepage_articles(limit * 2)  # Get more for better selection
                if homepage_articles:
                    # 메인 페이지 기사는 높은 우선순위
                    for article in homepage_articles:
                        article['relevance_score'] = 3.0  # 최상위 우선순위
                    all_articles.extend(homepage_articles)
                    logger.info("Homepage: {} articles collected".format(len(homepage_articles)))
                
                # Method 2: Enhanced section scraping (RSS discontinued)
                # Skip RSS since all feeds return 404
                logger.info("Skipping RSS feeds (discontinued), using enhanced section scraping")
                
                # Method 3: Enhanced section scraping with more sources
                if len(all_articles) < limit * 2:  # Get more articles to compensate for no RSS
                    section_articles = self._get_enhanced_section_articles(limit * 2)
                    if section_articles:
                        # URL 및 제목 기반 중복 제거 (더 엄격한 중복 체크)
                        existing_urls = {article['url'] for article in all_articles}
                        existing_titles = {article['title'] for article in all_articles}
                        new_section_articles = [
                            article for article in section_articles 
                            if article['url'] not in existing_urls and article['title'] not in existing_titles
                        ]
                        
                        # 섹션 기사는 기본 우선순위
                        for article in new_section_articles:
                            article['relevance_score'] = 1.0
                        
                        all_articles.extend(new_section_articles)
                        logger.info("Sections: {} new articles collected".format(len(new_section_articles)))
                
                # 최종 기사 선택
                # 1. 우선순위로 정렬
                all_articles.sort(key=lambda x: (
                    x.get('relevance_score', 0),  # 우선순위 점수
                    'OYT' in x.get('url', ''),    # OYT 코드 포함 여부
                    len(x.get('summary', '')),    # 요약 길이
                    x.get('image_url', '') != ''  # 이미지 존재 여부
                ), reverse=True)
                
                # 2. 중복 제거 (URL과 제목 모두 고려)
                seen_urls = set()
                seen_titles = set()
                unique_articles = []
                
                for article in all_articles:
                    url = article['url']
                    title = article['title']
                    
                    if url not in seen_urls and title not in seen_titles:
                        seen_urls.add(url)
                        seen_titles.add(title)
                        unique_articles.append(article)
                
                final_articles = unique_articles[:limit]
                
                if final_articles:
                    logger.info("Total: {} unique articles returned (requested: {})".format(len(final_articles), limit))
                    return final_articles
                else:
                    logger.info("Multi-source approach failed, falling back to news category")
                    return self.get_latest_news('news', limit)
            
            # 카테고리별 URL 매핑 (일본어 메인 사이트 사용)
            category_urls = {
                'all': None,  # RSS로 처리됨
                'news': 'https://www.yomiuri.co.jp/national',
                'business': 'https://www.yomiuri.co.jp/economy', 
                'sports': 'https://www.yomiuri.co.jp/sports/',  # 실제 스포츠 섹션
                'sport': 'https://www.yomiuri.co.jp/sports/',
                'tech': 'https://www.yomiuri.co.jp/science/',  # 실제 과학 섹션
                'technology': 'https://www.yomiuri.co.jp/science/',
                'world': 'https://www.yomiuri.co.jp/world',
                'culture': 'https://www.yomiuri.co.jp/culture/',  # 문화 섹션
                'opinion': 'https://www.yomiuri.co.jp/editorial'
            }
            
            # 기본 카테고리 처리
            url = category_urls.get(category)
            if not url:
                # URL이 없으면 RSS로 폴백
                logger.info("Yomiuri {} URL 없음, RSS 시도".format(category))
                return self._get_rss_articles('national', limit)
            
            logger.info("Yomiuri 최신 뉴스 가져오기: {}".format(url))
            
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            articles = self._extract_search_results(response.text, limit)
            logger.info("Yomiuri 최신 뉴스 {}개 수집".format(len(articles)))
            
            # 결과가 없거나 적으면 RSS로 fallback
            if not articles or len(articles) < limit // 2:
                logger.info("Yomiuri 최신 뉴스 결과 부족, RSS로 fallback")
                rss_articles = self._get_rss_articles('latest', limit)
                if rss_articles:
                    return rss_articles
                return self.search_news('breaking news', limit)
            
            return articles
            
        except Exception as e:
            logger.error("Yomiuri 최신 뉴스 가져오기 실패: {}".format(e))
            # 404나 다른 오류 시 search_news로 fallback
            logger.info("Yomiuri 최신 뉴스 실패, 검색으로 fallback")
            try:
                return self.search_news('breaking news', limit)
            except Exception as fallback_error:
                logger.error("Yomiuri fallback 검색도 실패: {}".format(fallback_error))
                return []
    
    def _get_rss_articles(self, feed_type='trending', limit=10):
        """RSS 피드에서 기사 추출 - RSS 중단으로 인한 스킵"""
        # Yomiuri has discontinued all RSS feeds (return 404)
        # Skip RSS attempts to avoid timeout delays and error logs
        logger.info("Yomiuri RSS feeds discontinued, skipping RSS retrieval")
        return []
    

    
    def _extract_rss_summary(self, entry):
        """RSS 엔트리에서 요약 추출"""
        # 다양한 요약 필드 시도
        summary_fields = ['summary', 'description', 'content']
        
        for field in summary_fields:
            if hasattr(entry, field):
                content = getattr(entry, field)
                if content:
                    # HTML 태그 제거
                    if hasattr(content, 'value'):
                        content = content.value
                    elif isinstance(content, list) and content:
                        content = content[0].get('value', str(content[0]))
                    
                    # BeautifulSoup으로 HTML 태그 정리
                    soup = BeautifulSoup(str(content), 'html.parser')
                    text = soup.get_text(strip=True)
                    
                    if text and len(text) > 20:
                        return text[:300] + "..." if len(text) > 300 else text
        
        # 요약이 없으면 제목 사용
        title = entry.get('title', '')
        return title[:200] + "..." if len(title) > 200 else title
    
    def _extract_rss_date(self, entry):
        """RSS 엔트리에서 날짜 추출"""
        # RSS 날짜 필드들 시도
        date_fields = ['published', 'updated', 'pubDate']
        
        for field in date_fields:
            if hasattr(entry, field + '_parsed'):
                date_tuple = getattr(entry, field + '_parsed')
                if date_tuple:
                    try:
                        date_obj = datetime(*date_tuple[:6])
                        return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                    except:
                        continue
            elif hasattr(entry, field):
                date_str = getattr(entry, field)
                if date_str:
                    try:
                        # feedparser가 파싱한 시간 사용
                        return date_str
                    except:
                        continue
        
        # 기본값: 현재 시간
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    def _extract_rss_image(self, entry):
        """Enhanced RSS image extraction with web scraping fallback"""
        try:
            # Method 1: enclosure 태그에서 이미지 찾기
            if hasattr(entry, 'enclosures') and entry.enclosures:
                for enclosure in entry.enclosures:
                    if enclosure.get('type', '').startswith('image/'):
                        return enclosure.get('href', '')
            
            # Method 2: media:content 태그에서 찾기
            if hasattr(entry, 'media_content') and entry.media_content:
                for media in entry.media_content:
                    if media.get('type', '').startswith('image/'):
                        return media.get('url', '')
            
            # Method 3: content에서 이미지 태그 찾기
            if hasattr(entry, 'content') and entry.content:
                content = entry.content[0].value if isinstance(entry.content, list) else entry.content
                soup = BeautifulSoup(str(content), 'html.parser')
                img = soup.find('img')
                if img:
                    return img.get('src', '')
            
            # Method 4: summary에서 이미지 태그 찾기
            if hasattr(entry, 'summary') and entry.summary:
                soup = BeautifulSoup(entry.summary, 'html.parser')
                img = soup.find('img')
                if img:
                    return img.get('src', '')
            

                    
        except Exception as e:
            logger.debug("RSS image extraction failed: {}".format(e))
        
        return ''
    
    def _get_trending_from_homepage(self, limit=10):
        """메인 페이지에서 트렌딩 뉴스 추출"""
        try:
            logger.info("Yomiuri 메인 페이지에서 트렌딩 뉴스 추출 시도")
            
            # 메인 페이지 접근
            response = requests.get(self.base_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = []
            found_urls = set()
            
            # 메인 페이지의 뉴스 제목들 추출 - OYT 코드 포함 링크만 사용 (확실한 뉴스 기사)
            title_elements = soup.select('a[href*="OYT"]')
            
            logger.info("Yomiuri 메인 페이지에서 {}개 제목 링크 발견".format(len(title_elements)))
            
            for elem in title_elements:
                try:
                    # 제목과 URL 추출
                    title = elem.get_text(strip=True)
                    url = elem.get('href', '')
                    
                    if not title or not url or len(title) < 15:
                        continue
                    
                    # URL 정규화
                    if url.startswith('/'):
                        url = self.base_url + url
                    elif not url.startswith('http'):
                        continue
                    
                    # Yomiuri URL 확인 및 중복 제거
                    if 'yomiuri.co.jp' not in url or url in found_urls:
                        continue
                    
                    # 뉴스 기사 URL 패턴 확인 - OYT 코드 포함만 허용 (가장 확실한 뉴스 기사)
                    import re
                    if not re.search(r'/\d{8}-OYT\d+T\d+/', url):
                        # OYT 코드가 없으면 뉴스 기사가 아님
                        continue
                    
                    found_urls.add(url)
                    
                    # 이미지 찾기 (부모 요소에서 검색)
                    image_url = ''
                    parent = elem.find_parent()
                    if parent:
                        for _ in range(3):  # 최대 3단계 부모까지 검색
                            img_elem = parent.find('img')
                            if img_elem:
                                image_url = img_elem.get('src', '') or img_elem.get('data-src', '')
                                if image_url:
                                    # 이미지 URL 정규화
                                    if image_url.startswith('//'):
                                        image_url = 'https:' + image_url
                                    elif image_url.startswith('/'):
                                        image_url = self.base_url + image_url
                                    break
                            parent = parent.find_parent()
                            if not parent:
                                break
                    
                    # 카테고리 추출
                    category = self._extract_category_from_content(title, '', url)
                    
                    # 요약 생성 (제목 기반)
                    summary = title[:150] + "..." if len(title) > 150 else title
                    
                    # 날짜 (현재 시간을 기본값으로 - 트렌딩이므로 최신)
                    published_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
                    
                    article = {
                        'title': title,
                        'url': url,
                        'summary': summary,
                        'published_date': published_date,
                        'source': 'Yomiuri Shimbun',
                        'category': category,
                        'scraped_at': datetime.now().isoformat(),
                        'relevance_score': 2,  # 메인 페이지 트렌딩은 높은 관련성
                        'image_url': image_url or self._get_fallback_image(category)
                    }
                    
                    articles.append(article)
                    
                    if len(articles) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug("Yomiuri 메인 페이지 기사 처리 실패: {}".format(e))
                    continue
            
            logger.info("Yomiuri 메인 페이지에서 {}개 기사 추출 완료".format(len(articles)))
            return articles[:limit]
            
        except Exception as e:
            logger.error("Yomiuri 메인 페이지 처리 실패: {}".format(e))
            return []
    
    def _get_fallback_image(self, category):
        """카테고리별 기본 이미지 URL 반환"""
        fallback_images = {
            'news': 'https://www.yomiuri.co.jp/media/2024/01/20240101-OYT8I50001-1.jpg',
            'politics': 'https://www.yomiuri.co.jp/media/2024/01/20240101-OYT8I50002-1.jpg',
            'business': 'https://www.yomiuri.co.jp/media/2024/01/20240101-OYT8I50003-1.jpg',
            'sports': 'https://www.yomiuri.co.jp/media/2024/01/20240101-OYT8I50004-1.jpg',
            'technology': 'https://www.yomiuri.co.jp/media/2024/01/20240101-OYT8I50005-1.jpg',
            'world': 'https://www.yomiuri.co.jp/media/2024/01/20240101-OYT8I50006-1.jpg'
        }
        return fallback_images.get(category, fallback_images['news'])
    
    def _extract_enhanced_image(self, elem):
        """Enhanced image extraction with multiple fallback strategies"""
        try:
            # Strategy 1: Direct img in element
            img_elem = elem.find('img')
            if img_elem:
                image_url = (img_elem.get('src', '') or 
                           img_elem.get('data-src', '') or 
                           img_elem.get('data-lazy', '') or
                           img_elem.get('data-original', ''))
                if image_url:
                    return self._normalize_image_url(image_url)
            
            # Strategy 2: Search parent elements (up to 4 levels)
            parent = elem.find_parent()
            for level in range(4):
                if not parent:
                    break
                    
                # Look for img in parent
                img_elem = parent.find('img')
                if img_elem:
                    image_url = (img_elem.get('src', '') or 
                               img_elem.get('data-src', '') or 
                               img_elem.get('data-lazy', '') or
                               img_elem.get('data-original', ''))
                    if image_url:
                        return self._normalize_image_url(image_url)
                
                # Look for background-image in style
                style = parent.get('style', '')
                if 'background-image' in style:
                    import re
                    bg_match = re.search(r'background-image\s*:\s*url\(["\']?([^"\')]+)["\']?\)', style)
                    if bg_match:
                        return self._normalize_image_url(bg_match.group(1))
                
                parent = parent.find_parent()
            
            # Strategy 3: Search sibling elements
            siblings = elem.find_next_siblings(['img', 'figure', 'picture'])
            for sibling in siblings[:3]:  # Check first 3 siblings
                if sibling.name == 'img':
                    image_url = (sibling.get('src', '') or 
                               sibling.get('data-src', '') or 
                               sibling.get('data-lazy', ''))
                    if image_url:
                        return self._normalize_image_url(image_url)
                else:
                    img_elem = sibling.find('img')
                    if img_elem:
                        image_url = (img_elem.get('src', '') or 
                                   img_elem.get('data-src', '') or 
                                   img_elem.get('data-lazy', ''))
                        if image_url:
                            return self._normalize_image_url(image_url)
            
            return ''
            
        except Exception as e:
            logger.debug("Enhanced 이미지 추출 실패: {}".format(e))
            return ''
    
    def _process_article_link(self, link, articles, found_urls, relevance_score=1.0):
        """기사 링크를 처리하여 기사 정보를 추출하고 articles 리스트에 추가"""
        # 제목 추출
        title_text = link.get_text(strip=True)
        if not title_text or len(title_text) < 10:
            return
            
        # Encode/decode to handle Unicode properly  
        try:
            title = title_text.encode('utf-8', 'ignore').decode('utf-8')
        except:
            title = title_text
            
        url = link.get('href', '')
        if not url:
            return
        
        # URL normalization
        if url.startswith('/'):
            url = self.base_url + url
        elif not url.startswith('http'):
            return
        
        # Basic validation
        if 'yomiuri.co.jp' not in url or url in found_urls:
            return
        
        # Enhanced URL validation - accept more patterns
        valid_patterns = [
            r'/\d{8}-OYT\d+T\d+/',  # Original OYT pattern
            r'/\d{4}/\d{2}/\d{2}/',  # Date-based URLs
            r'/(news|national|politics|economy|world|sports|culture)/',  # Section URLs
            r'/article/\d+',  # Article ID pattern
        ]
        
        is_valid_article = any(re.search(pattern, url) for pattern in valid_patterns)
        if not is_valid_article:
            return
        
        found_urls.add(url)
        
        # Extract image with error handling
        image_url = ''
        try:
            image_url = self._extract_enhanced_image(link)
        except:
            pass
        
        # Extract category
        category = self._extract_category_from_content(title, '', url)
        
        # Create summary
        summary = title[:150] + "..." if len(title) > 150 else title
        
        article = {
            'title': title,
            'url': url,
            'summary': summary,
            'published_date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),
            'source': 'Yomiuri Shimbun',
            'category': category,
            'scraped_at': datetime.now().isoformat(),
            'relevance_score': relevance_score,
            'image_url': image_url or self._get_fallback_image(category)
        }
        
        articles.append(article)
        
    def _normalize_image_url(self, image_url):
        """Normalize image URL to absolute URL"""
        if not image_url:
            return ''
            
        if image_url.startswith('http'):
            return image_url
        elif image_url.startswith('//'):
            return 'https:' + image_url
        elif image_url.startswith('/'):
            return self.base_url + image_url
        else:
            return self.base_url + '/' + image_url
    
    def _get_diversified_rss_articles(self, limit=10):
        """Get articles from RSS feeds - disabled (feeds discontinued)"""
        # All Yomiuri RSS feeds have been discontinued (404 errors)
        logger.info("RSS feeds discontinued by Yomiuri, returning empty list")
        return []
    
    def _get_backup_rss_articles(self, limit=5):
        """Try backup RSS feeds when primary feeds fail"""
        try:
            for backup_url in self.backup_rss_feeds:
                try:
                    logger.info("백업 RSS 시도: {}".format(backup_url))
                    feed = feedparser.parse(backup_url)
                    
                    if not feed.entries:
                        continue
                    
                    articles = []
                    for entry in feed.entries[:limit]:
                        try:
                            title = entry.get('title', '').strip()
                            url = entry.get('link', '').strip()
                            
                            if not title or not url:
                                continue
                            
                            summary = self._extract_rss_summary(entry)
                            published_date = self._extract_rss_date(entry)
                            image_url = self._extract_rss_image(entry)
                            category = self._extract_category_from_url(url)
                            
                            article = {
                                'title': title,
                                'url': url,
                                'summary': summary,
                                'published_date': published_date,
                                'source': 'Yomiuri Backup RSS',
                                'category': category,
                                'scraped_at': datetime.now().isoformat(),
                                'relevance_score': 1,
                                'image_url': image_url or self._get_fallback_image(category)
                            }
                            
                            articles.append(article)
                            
                        except Exception as e:
                            logger.debug("백업 RSS 엔트리 처리 실패: {}".format(e))
                            continue
                    
                    if articles:
                        logger.info("백업 RSS {}에서 {}개 기사 수집".format(backup_url, len(articles)))
                        return articles
                        
                except Exception as e:
                    logger.debug("백업 RSS {} 실패: {}".format(backup_url, e))
                    continue
            
            return []
            
        except Exception as e:
            logger.error("백업 RSS 처리 실패: {}".format(e))
            return []
    
    def _get_enhanced_section_articles(self, limit=20):
        """Enhanced scraping from multiple section pages with better extraction"""
        try:
            logger.info("Enhanced 섹션 페이지에서 기사 수집 시도")
            
            all_articles = []
            articles_per_section = max(2, limit // len(self.enhanced_section_urls))
            
            for section_url in self.enhanced_section_urls:
                if len(all_articles) >= limit:
                    break
                    
                try:
                    logger.info("Enhanced 섹션 페이지 스크래핑: {}".format(section_url))
                    response = requests.get(section_url, headers=self.headers, timeout=15)
                    response.raise_for_status()
                    
                    # Use enhanced extraction with better selectors
                    section_articles = self._extract_enhanced_articles(response.text, articles_per_section, section_url)
                    if section_articles:
                        # Mark as section-sourced with higher priority
                        for article in section_articles:
                            article['relevance_score'] = 1.5  # Higher than before
                            article['source'] = 'Yomiuri Shimbun (Enhanced)'
                        
                        all_articles.extend(section_articles)
                        logger.info("Enhanced 섹션 {}에서 {}개 기사 수집".format(section_url, len(section_articles)))
                    
                except Exception as e:
                    logger.debug("Enhanced 섹션 {} 스크래핑 실패: {}".format(section_url, e))
                    continue
            
            logger.info("총 Enhanced 섹션에서 {}개 기사 수집 완료".format(len(all_articles)))
            return all_articles[:limit]
            
        except Exception as e:
            logger.error("Enhanced 섹션 페이지 처리 실패: {}".format(e))
            return []
    
    def _extract_enhanced_articles(self, html_content, limit, base_url):
        """Enhanced article extraction with better selectors"""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            found_urls = set()
            
            # Enhanced selectors for better article detection
            enhanced_selectors = [
                'a[href*="OYT"]',  # Classic Yomiuri article pattern
                '.p-list-item a[href]',  # List items
                '.c-list-item a[href]',  # Content list items  
                '.news-item a[href]',   # News items
                '.article-item a[href]', # Article items
                '.story a[href]',       # Story links
                'article a[href]',      # Article tags
                '.content a[href]',     # Content sections
                'h2 a[href]',          # Headlines in h2
                'h3 a[href]',          # Headlines in h3
                '.title a[href]',      # Title links
                '.headline a[href]',   # Headlines
                'a[href*="/national/"]', # National news
                'a[href*="/politics/"]', # Politics
                'a[href*="/economy/"]',  # Economy
                'a[href*="/world/"]',    # World news
                'a[href*="/sports/"]',   # Sports
                'a[href*="/culture/"]',  # Culture
                'a[href*="/science/"]',  # Science
                'a[href*="/local/"]',    # Local news
                'a[href*="/life/"]',     # Lifestyle
            ]
            
            for selector in enhanced_selectors:
                if len(articles) >= limit:
                    break
                    
                try:
                    elements = soup.select(selector)
                    logger.debug("Enhanced selector '{}': {} elements".format(selector, len(elements)))
                    
                    for elem in elements:
                        if len(articles) >= limit:
                            break
                            
                        try:
                            self._process_enhanced_article_link(elem, articles, found_urls, base_url)
                        except Exception as e:
                            logger.debug("Enhanced article processing failed: {}".format(e))
                            continue
                            
                except Exception as e:
                    logger.debug("Enhanced selector '{}' failed: {}".format(selector, e))
                    continue
            
            logger.info("Enhanced extraction: {} articles from {}".format(len(articles), base_url))
            return articles[:limit]
            
        except Exception as e:
            logger.error("Enhanced article extraction failed: {}".format(e))
            return []
    
    def _process_enhanced_article_link(self, link, articles, found_urls, base_url):
        """Enhanced processing of article links with better validation"""
        try:
            # Get title
            title_text = link.get_text(strip=True)
            if not title_text or len(title_text) < 10:
                return
                
            # Clean up title
            title = title_text.encode('utf-8', 'ignore').decode('utf-8')
            
            # Get URL
            url = link.get('href', '')
            if not url:
                return
            
            # Normalize URL
            if url.startswith('/'):
                url = self.base_url + url
            elif not url.startswith('http'):
                return
            
            # Validate URL and avoid duplicates
            if 'yomiuri.co.jp' not in url or url in found_urls:
                return
            
            # Enhanced URL pattern validation
            valid_patterns = [
                r'/\d{8}-OYT\d+T\d+/',  # OYT pattern
                r'/\d{4}/\d{2}/\d{2}/',  # Date-based
                r'/(national|politics|economy|world|sports|culture|science|local|life|editorial)/',
                r'/article/',
                r'/news/',
            ]
            
            is_valid = any(re.search(pattern, url) for pattern in valid_patterns)
            if not is_valid:
                return
            
            found_urls.add(url)
            
            # Extract additional info
            image_url = self._extract_enhanced_image(link)
            category = self._extract_category_from_url(url)
            
            # Better summary
            summary = self._generate_better_summary(title, link, base_url)
            
            article = {
                'title': title,
                'url': url,
                'summary': summary,
                'published_date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),
                'source': 'Yomiuri Shimbun',
                'category': category,
                'scraped_at': datetime.now().isoformat(),
                'relevance_score': 1.5,
                'image_url': image_url or self._get_fallback_image(category)
            }
            
            articles.append(article)
            
        except Exception as e:
            logger.debug("Enhanced article link processing failed: {}".format(e))
    
    def _generate_better_summary(self, title, link_elem, base_url):
        """Generate better summary by looking for description text near the link"""
        try:
            # Try to find summary in nearby elements
            parent = link_elem.find_parent()
            for _ in range(3):  # Check up to 3 parent levels
                if not parent:
                    break
                    
                # Look for description elements
                desc_selectors = ['.description', '.excerpt', '.summary', '.lead', 'p']
                for selector in desc_selectors:
                    desc_elem = parent.find(selector)
                    if desc_elem:
                        desc_text = desc_elem.get_text(strip=True)
                        if desc_text and len(desc_text) > 30 and desc_text != title:
                            return desc_text[:200] + "..." if len(desc_text) > 200 else desc_text
                
                parent = parent.find_parent()
            
            # Fallback to title-based summary
            return title[:150] + "..." if len(title) > 150 else title
            
        except Exception:
            return title[:150] + "..." if len(title) > 150 else title
    
    def _get_enhanced_homepage_articles(self, limit=10):
        """Enhanced homepage scraping - removes OYT restriction, adds broader selectors"""
        try:
            logger.info("Enhanced homepage scraping attempt")
            
            response = requests.get(self.base_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = []
            found_urls = set()
            
            # 最新主要ニュース 섹션 찾기 - 더 많은 방법으로 시도
            main_news_section = None
            
            # 방법 1: 텍스트로 섹션 찾기
            for tag in soup.find_all(['section', 'div', 'article']):
                if tag.string and '最新主要ニュース' in tag.string:
                    main_news_section = tag.parent if tag.name != 'section' else tag
                    break
            
            # 방법 2: 클래스나 id로 찾기
            if not main_news_section:
                main_news_section = soup.find(['section', 'div'], class_=lambda x: x and ('main-news' in x or 'latest-news' in x or 'top-news' in x))
            
            # 방법 3: h2/h3 헤더로 찾기
            if not main_news_section:
                header = soup.find(['h2', 'h3'], string=lambda x: x and '最新主要ニュース' in x)
                if header:
                    main_news_section = header.find_parent(['section', 'div', 'article'])
            
            if main_news_section:
                logger.info("最新主要ニュース 섹션 발견")
                
                # 섹션 내의 모든 기사 링크 찾기
                # 부모 요소로부터 더 넓은 범위의 링크를 찾음
                parent_container = main_news_section.find_parent(['div', 'section']) or main_news_section
                main_news_links = parent_container.find_all('a', href=True)
                
                # 유효한 뉴스 링크만 필터링
                valid_links = []
                for link in main_news_links:
                    href = link.get('href', '')
                    # 뉴스 기사 패턴 확인
                    if any(pattern in href for pattern in ['/OYT', '/news/', '/national/', '/politics/', '/economy/', '/world/', '/sports/', '/culture/']):
                        valid_links.append(link)
                
                if valid_links:
                    logger.info("最新主要ニュース 섹션에서 {}개의 유효한 링크 발견".format(len(valid_links)))
                    for link in valid_links:
                        if len(articles) >= limit:
                            break
                        try:
                            self._process_article_link(link, articles, found_urls, relevance_score=4.0)  # 最新主要ニュース는 최고 우선순위
                        except Exception as e:
                            logger.debug("最新主要ニュース 링크 처리 실패: {}".format(str(e)))
            else:
                logger.info("最新主要ニュース 섹션을 찾을 수 없음, 대체 방법 시도")
                
                # 最新主要ニュース 섹션을 못 찾은 경우, 메인 페이지 상단의 주요 기사들을 수집
                top_articles = soup.select('.top-article a[href], .main-article a[href], .featured a[href]')
                for link in top_articles[:limit]:
                    try:
                        self._process_article_link(link, articles, found_urls, relevance_score=3.5)
                    except Exception as e:
                        logger.debug("상단 기사 처리 실패: {}".format(str(e)))
            
            # 다른 주요 섹션들의 기사도 수집
            enhanced_selectors = [
                'a[href*="OYT"]',  # Original OYT pattern (high priority)
                '.news-top a[href]',  # Top news section
                '.breaking-news a[href]',  # Breaking news
                '.headline a[href]',  # Headlines
                'a[href*="/national/"]',  # National news
                'a[href*="/politics/"]',  # Politics  
                'a[href*="/economy/"]',  # Economy
                'a[href*="/world/"]',  # World news
                'a[href*="/sports/"]',  # Sports
                'a[href*="/culture/"]',  # Culture
                'a[href*="/news/"]',  # News section links
            ]
            
            for selector_priority, selector in enumerate(enhanced_selectors):
                if len(articles) >= limit:
                    break
                    
                try:
                    elements = soup.select(selector)
                    logger.info("Selector '{}': {} elements found".format(selector, len(elements)))
                    
                    for elem in elements:
                        if len(articles) >= limit:
                            break
                            
                        try:
                            # Priority scoring based on selector position
                            relevance_score = 3 - (selector_priority * 0.1)
                            self._process_article_link(elem, articles, found_urls, relevance_score)
                            
                        except Exception as e:
                            logger.debug("Homepage article processing failed: {}".format(str(e)))
                            continue
                            
                except Exception as e:
                    logger.debug("Selector '{}' failed: {}".format(selector, str(e)))
                    continue
            
            logger.info("Enhanced homepage extracted {} articles".format(len(articles)))
            return articles[:limit]
            
        except Exception as e:
            logger.error("Enhanced homepage processing failed: {}".format(str(e)))
            return [] 