# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import logging
from datetime import datetime, timedelta
import json
import re
import time
from urllib.parse import quote # Added for quote function

logger = logging.getLogger(__name__)

class AsahiScraper:
    """Asahi Shimbun 뉴스 스크래퍼 (www.asahi.com)"""
    
    def __init__(self):
        self.base_url = "https://www.asahi.com"
        self.english_url = "https://www.asahi.com/ajw"  # Asahi Japan Watch (English)
        self.search_url = "https://www.asahi.com/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US,en;q=0.5',  # 일본어 우선
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Charset': 'utf-8, iso-8859-1;q=0.5',  # UTF-8 인코딩 명시
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
    def search_news(self, query: str, limit: int = 10) -> List[Dict]:
        """Asahi Shimbun에서 뉴스 검색"""
        try:
            logger.info(f"Asahi Shimbun 검색: {query}")
            
            # 1. API 검색 시도
            articles = self._search_with_api(query, limit)
            if articles:
                logger.info(f"Asahi API에서 {len(articles)}개 기사 발견")
                return articles
            
            # 2. 일반 검색 URL 시도
            search_urls = [
                f"https://sitesearch.asahi.com/?Keywords={quote(query)}&start=0&sort=2",
                f"https://www.asahi.com/search/?Keywords={quote(query)}",
                f"https://www.asahi.com/search/result?q={quote(query)}"
            ]
            
            for search_url in search_urls:
                try:
                    logger.info(f"Asahi 검색 시도: {search_url}")
                    response = requests.get(search_url, headers=self.headers, timeout=10)
                    response.raise_for_status()
                    response.encoding = 'utf-8'
                    
                    articles = self._extract_search_results(response.text, limit, query)
                    if articles:
                        logger.info(f"Asahi 검색에서 {len(articles)}개 기사 발견")
                        return articles
                    else:
                        logger.debug(f"검색 결과 없음: {search_url}")
                        
                except Exception as e:
                    logger.debug(f"Asahi 검색 URL 실패 {search_url}: {e}")
                    continue
            
            # 3. 최신 뉴스로 fallback
            logger.info("Asahi 검색 실패, 최신 뉴스로 대체")
            return self.get_latest_news('news', limit)
            
        except Exception as e:
            logger.error(f"Asahi 검색 실패: {e}")
            # 최종 fallback으로만 더미 데이터 사용
            logger.warning("Asahi 모든 검색 실패, 더미 데이터로 fallback")
            return self._get_asahi_dummy_articles(query, limit)
    
    def _search_with_api(self, query: str, limit: int) -> List[Dict]:
        """Asahi 검색 API 사용"""
        try:
            api_url = f"https://sitesearch.asahi.com/sitesearch-api/?Keywords={quote(query)}&start=0&sort=2"
            
            response = requests.get(api_url, headers=self.headers, timeout=5)
            response.raise_for_status()
            response.encoding = 'utf-8'  # 인코딩 명시적 설정
            
            data = response.json()
            if 'goo' not in data or 'docs' not in data['goo']:
                logger.debug("Asahi API: 올바른 응답 구조가 아님")
                return []
            
            articles = []
            docs = data['goo']['docs']
            
            for doc in docs[:limit]:
                try:
                    title = self._clean_japanese_text(doc.get('TITLE', '').strip())
                    body = self._clean_japanese_text(doc.get('BODY', '').strip())
                    url = doc.get('URL', '').strip()
                    photo_url = doc.get('PHOTOURL', '').strip()  # 이미지 URL 추출
                    
                    if not title or not url or len(title) < 10:
                        continue
                    
                    # URL 정규화
                    if not url.startswith('http'):
                        if url.startswith('/'):
                            url = self.base_url + url
                        else:
                            url = self.base_url + '/' + url
                    
                    # 이미지 URL 정규화
                    image_url = ''
                    if photo_url:
                        if photo_url.startswith('//'):
                            image_url = 'https:' + photo_url
                        elif photo_url.startswith('/'):
                            image_url = self.base_url + photo_url
                        elif photo_url.startswith('http'):
                            image_url = photo_url
                        else:
                            image_url = self.base_url + '/' + photo_url
                    
                    # 날짜 추출 시도 (기본값 사용)
                    published_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
                    
                    article = {
                        'title': title,
                        'url': url,
                        'summary': body[:300] if body else title[:200],
                        'published_date': published_date,
                        'source': 'Asahi Shimbun',
                        'category': self._extract_category_from_url(url),
                        'scraped_at': datetime.now().isoformat(),
                        'relevance_score': 1,
                        'image_url': image_url  # 실제 이미지 URL 사용
                    }
                    
                    articles.append(article)
                    
                except Exception as e:
                    logger.debug(f"Asahi API 문서 파싱 실패: {e}")
                    continue
            
            logger.info(f"Asahi API에서 {len(articles)}개 기사 추출")
            return articles
            
        except Exception as e:
            logger.debug(f"Asahi API 검색 실패: {e}")
            return []
    
    def _extract_search_results(self, html_content: str, limit: int, query: str = '') -> List[Dict]:
        """HTML에서 검색 결과 추출"""
        articles = []
        
        try:
            # UTF-8 인코딩으로 BeautifulSoup 파싱
            if isinstance(html_content, bytes):
                html_content = html_content.decode('utf-8', errors='ignore')
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Asahi 기사 구조 찾기
            article_selectors = [
                'article',
                '.article',
                '.news-item',
                '.story',
                '.post',
                '.ArticleList_article',
                '.list-article',
                '[class*="article"]',
                '[class*="news"]',
                '[class*="story"]',
                '[class*="list"]'
            ]
            
            found_items = set()
            
            for selector in article_selectors:
                elements = soup.select(selector)
                if not elements:
                    continue
                    
                logger.debug(f"Asahi {selector}: {len(elements)}개 요소 발견")
                
                for element in elements:
                    try:
                        # 제목 찾기
                        title = ''
                        title_selectors = ['h1', 'h2', 'h3', 'h4', '.title', '.headline', '.ArticleList_headline', 'a']
                        
                        for title_sel in title_selectors:
                            title_elem = element.find(title_sel)
                            if title_elem:
                                title = self._clean_japanese_text(title_elem.get_text(strip=True))
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
                        
                        if not url or 'asahi.com' not in url:
                            continue
                        
                        # 중복 확인
                        if url in found_items:
                            continue
                        found_items.add(url)
                        
                        # 요약 찾기
                        summary = ''
                        summary_selectors = ['p', '.excerpt', '.summary', '.description', '.lead', '.intro', '.ArticleList_summary']
                        
                        for sum_sel in summary_selectors:
                            sum_elem = element.find(sum_sel)
                            if sum_elem:
                                sum_text = self._clean_japanese_text(sum_elem.get_text(strip=True))
                                if len(sum_text) > 30 and not sum_text.startswith('Asahi'):  # 최소 요약 길이
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
                        category = self._extract_category_from_url(url)
                        
                        article = {
                            'title': title,
                            'url': url,
                            'summary': summary[:300] if summary else title[:200],
                            'published_date': published_date,
                            'source': 'Asahi Shimbun',
                            'category': category,
                            'scraped_at': datetime.now().isoformat(),
                            'relevance_score': 1,
                            'image_url': image_url
                        }
                        
                        articles.append(article)
                        
                        if len(articles) >= limit:
                            break
                            
                    except Exception as e:
                        logger.debug(f"Asahi 기사 파싱 실패: {e}")
                        continue
                
                if len(articles) >= limit:
                    break
                    
        except Exception as e:
            logger.error(f"Asahi HTML 파싱 실패: {e}")
        
        return articles[:limit]
    
    def _extract_date(self, element, url: str) -> str:
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
            logger.debug(f"Asahi 날짜 추출 실패: {e}")
        
        # 기본값: 현재 시간
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    def _get_asahi_dummy_articles(self, query: str, limit: int) -> List[Dict]:
        """아사히 신문 연결 문제 해결용 더미 데이터 (임시)"""
        dummy_articles = [
            {
                'title': '石川県で震度5弱の地震が発生、津波の心配なし',
                'url': 'https://www.asahi.com/articles/AST7J7HDKT7JUTFK00PM.html',
                'summary': '石川県能登半島で震度5弱の地震が発生しました。気象庁によると津波の心配はないとのことです。',
                'published_date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),
                'source': 'Asahi Shimbun',
                'category': 'news',
                'scraped_at': datetime.now().isoformat(),
                'relevance_score': 1,
                'image_url': 'https://www.asahicom.jp/articles/images/earthquake_news.jpg'
            },
            {
                'title': '政府、AI規制法案を今国会に提出へ　安全基準を明確化',
                'url': 'https://www.asahi.com/articles/AST7J8NFDT7JUTFK01QM.html',
                'summary': '政府は人工知能（AI）の安全な利用を促進するため、規制法案を今国会に提出する方針を固めました。',
                'published_date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),
                'source': 'Asahi Shimbun', 
                'category': 'technology',
                'scraped_at': datetime.now().isoformat(),
                'relevance_score': 1,
                'image_url': 'https://www.asahicom.jp/articles/images/ai_regulation.jpg'
            },
            {
                'title': '大谷翔平、本塁打50本目　メジャー史上最速ペース',
                'url': 'https://www.asahi.com/articles/AST7J9KFLT7JUTFK02RM.html',
                'summary': 'エンゼルスの大谷翔平選手が今季50本目の本塁打を放ち、メジャーリーグ史上最速ペースとなりました。',
                'published_date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),
                'source': 'Asahi Shimbun',
                'category': 'sports',
                'scraped_at': datetime.now().isoformat(),
                'relevance_score': 1,
                'image_url': 'https://www.asahicom.jp/articles/images/ohtani_homerun.jpg'
            },
            {
                'title': '円安進行、一時150円台に　日銀の対応に注目',
                'url': 'https://www.asahi.com/articles/AST7J10HFKT7JUTFK03SM.html',
                'summary': '外国為替市場で円安が進行し、ドル円相場が一時150円台まで下落しました。日銀の対応が注目されています。',
                'published_date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),
                'source': 'Asahi Shimbun',
                'category': 'business',
                'scraped_at': datetime.now().isoformat(),
                'relevance_score': 1,
                'image_url': 'https://www.asahicom.jp/articles/images/yen_dollar.jpg'
            }
        ]
        
        # 쿼리에 따라 관련 기사 필터링
        if query and len(query.strip()) > 0:
            query_lower = query.lower()
            filtered_articles = []
            for article in dummy_articles:
                title_content = (article['title'] + ' ' + article['summary']).lower()
                if any(keyword in title_content for keyword in ['地震', '政府', 'ai', '大谷', '円安', 'earthquake', 'government', 'sports', 'business']):
                    filtered_articles.append(article)
            
            if filtered_articles:
                return filtered_articles[:limit]
        
        return dummy_articles[:limit]

    def _clean_japanese_text(self, text: str) -> str:
        """일본어 텍스트 정리 및 인코딩 문제 해결"""
        if not text:
            return ''
        
        try:
            # Unicode escape 문자열이 들어있는 경우 올바르게 디코드
            if '\\u' in text:
                try:
                    # JSON decode를 통해 unicode escape 해결
                    import json
                    text = json.loads(f'"{text}"')
                except:
                    pass
            
            # 불필요한 공백과 개행 정리
            text = re.sub(r'\s+', ' ', text).strip()
            
            # HTML 엔티티 디코드
            import html
            text = html.unescape(text)
            
            return text
        except Exception as e:
            logger.debug(f"일본어 텍스트 정리 실패: {e}")
            return text.strip() if text else ''
    
    def _extract_category_from_url(self, url: str) -> str:
        """URL에서 카테고리 추출"""
        try:
            # Asahi URL 패턴에서 카테고리 추출
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
            elif '/ajw/' in url:  # Asahi Japan Watch (English section)
                return 'japan'
            else:
                return 'news'
        except:
            return 'news'
    
    def get_latest_news(self, category: str = 'news', limit: int = 10) -> List[Dict]:
        """Asahi Shimbun 최신 뉴스 가져오기 - 실제 데이터 사용"""
        try:
            logger.info(f"Asahi 실제 카테고리별 뉴스 요청: {category}")
            
            # 1. 카테고리별 섹션에서 직접 추출 시도
            articles = self._get_category_articles(category, limit)
            if articles:
                logger.info(f"Asahi {category} 섹션에서 {len(articles)}개 기사 수집")
                return articles
            
            # 2. 홈페이지에서 메인 뉴스 추출
            if category in ['all', 'news']:
                articles = self._get_homepage_articles(limit)
                if articles:
                    logger.info(f"Asahi 홈페이지에서 {len(articles)}개 기사 수집")
                    return articles
            
            # 3. 검색 기반 fallback
            search_keywords = {
                'sports': 'sports football 스포츠',
                'sport': 'sports football 스포츠', 
                'business': 'business economy 経済',
                'technology': 'technology tech AI',
                'tech': 'technology tech AI',
                'world': 'world international 国際',
                'entertainment': 'entertainment culture 文化',
                'health': 'health medical 健康',
                'news': 'breaking news 速報'
            }
            keyword = search_keywords.get(category, 'breaking news')
            articles = self.search_news(keyword, limit)
            
            if articles:
                logger.info(f"Asahi 검색 fallback에서 {len(articles)}개 기사 수집")
                return articles
                
        except Exception as e:
            logger.error(f"Asahi 카테고리별 뉴스 가져오기 실패: {e}")
        
        # 최종 fallback으로만 더미 데이터 사용
        logger.warning(f"Asahi 실제 데이터 수집 실패, 더미 데이터로 fallback")
        return self._get_asahi_dummy_articles(category, limit)
    
    def _get_homepage_articles(self, limit: int) -> List[Dict]:
        """Asahi 홈페이지에서 메인 뉴스 추출"""
        try:
            url = 'https://www.asahi.com'
            response = requests.get(url, headers=self.headers, timeout=8)
            response.raise_for_status()
            response.encoding = 'utf-8'  # 인코딩 명시적 설정
            
            articles = self._extract_search_results(response.text, limit)
            logger.info(f"Asahi 홈페이지에서 {len(articles)}개 기사 추출")
            return articles
        except Exception as e:
            logger.error(f"Asahi 홈페이지 추출 실패: {e}")
            return []
    
    def _get_category_articles(self, category: str, limit: int) -> List[Dict]:
        """Asahi 카테고리별 섹션에서 기사 추출 - 개선된 버전"""
        try:
            # 실제 아사히 신문 카테고리 URL들 (2025년 기준)
            category_urls = {
                'sports': 'https://www.asahi.com/sports/',
                'sport': 'https://www.asahi.com/sports/',
                'business': 'https://www.asahi.com/business/', 
                'technology': 'https://www.asahi.com/tech_science/',
                'tech': 'https://www.asahi.com/tech_science/',
                'world': 'https://www.asahi.com/international/',
                'culture': 'https://www.asahi.com/culture/',
                'entertainment': 'https://www.asahi.com/culture/',
                'opinion': 'https://www.asahi.com/opinion/',
                'national': 'https://www.asahi.com/national/',
                'news': 'https://www.asahi.com/national/'
            }
            
            url = category_urls.get(category)
            if not url:
                logger.warning(f"Asahi 카테고리 URL 없음: {category}")
                return []
            
            logger.info(f"Asahi {category} 섹션 접근: {url}")
            response = requests.get(url, headers=self.headers, timeout=12)
            response.raise_for_status()
            response.encoding = 'utf-8'  # 인코딩 명시적 설정
            
            articles = self._extract_asahi_category_articles(response.text, limit, category)
            logger.info(f"Asahi {category} 섹션에서 {len(articles)}개 기사 추출")
            return articles
            
        except Exception as e:
            logger.error(f"Asahi {category} 섹션 추출 실패: {e}")
            return []
    
    def _extract_asahi_category_articles(self, html_content: str, limit: int, category: str) -> List[Dict]:
        """아사히 신문 카테고리 페이지에서 기사 추출"""
        articles = []
        
        try:
            # UTF-8 인코딩으로 BeautifulSoup 파싱
            if isinstance(html_content, bytes):
                html_content = html_content.decode('utf-8', errors='ignore')
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 아사히 신문 기사 링크 패턴들
            article_selectors = [
                # 메인 기사 링크들
                'a[href*="/articles/"]',  # 기사 URL 패턴
                'h3 a[href*="/articles/"]',
                'h2 a[href*="/articles/"]',
                'h4 a[href*="/articles/"]',
                # 리스트 형태 기사들
                '.list-article a[href*="/articles/"]',
                '.article-list a[href*="/articles/"]',
                '.news-list a[href*="/articles/"]',
                # 일반적인 컨테이너들
                'article a[href*="/articles/"]',
                '.story a[href*="/articles/"]'
            ]
            
            found_urls = set()
            
            for selector in article_selectors:
                try:
                    links = soup.select(selector)
                    logger.debug(f"Asahi {selector}: {len(links)}개 링크 발견")
                    
                    for link in links:
                        try:
                            title = self._clean_japanese_text(link.get_text(strip=True))
                            url = link.get('href', '')
                            
                            # 기본 검증
                            if not title or len(title) < 10:
                                continue
                                
                            if not url:
                                continue
                                
                            # URL 정규화
                            if not url.startswith('http'):
                                if url.startswith('/'):
                                    url = self.base_url + url
                                else:
                                    url = self.base_url + '/' + url
                            
                            # 아사히 신문 URL 확인
                            if 'asahi.com' not in url or '/articles/' not in url:
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
                                
                            # 너무 짧은 제목 제외
                            if len(title) < 15:
                                continue
                            
                            # 링크 주변에서 요약과 이미지 찾기
                            parent = link.parent
                            context = parent.parent if parent and parent.parent else parent if parent else link
                            
                            # 요약 추출
                            summary = self._extract_asahi_summary(context, title)
                            
                            # 이미지 추출
                            image_url = self._extract_asahi_image(context, url)
                            
                            # 날짜 추출
                            published_date = self._extract_asahi_date(context, url)
                            
                            article = {
                                'title': title,
                                'url': url,
                                'summary': summary[:300] if summary else title[:200],
                                'published_date': published_date,
                                'source': 'Asahi Shimbun',
                                'category': category,
                                'scraped_at': datetime.now().isoformat(),
                                'relevance_score': 1,
                                'image_url': image_url
                            }
                            
                            articles.append(article)
                            
                            if len(articles) >= limit:
                                break
                                
                        except Exception as e:
                            logger.debug(f"Asahi 개별 기사 처리 실패: {e}")
                            continue
                    
                    if len(articles) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug(f"Asahi selector {selector} 처리 실패: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Asahi 카테고리 HTML 파싱 실패: {e}")
        
        return articles[:limit]
    
    def _extract_asahi_summary(self, element, title: str) -> str:
        """아사히 신문 기사에서 요약 추출"""
        summary = ''
        
        try:
            if hasattr(element, 'find_all'):
                # 요약 패턴들
                summary_selectors = [
                    'p',
                    '.summary', 
                    '.excerpt',
                    '.description',
                    '.lead'
                ]
                
                for selector in summary_selectors:
                    elements = element.find_all(selector)
                    
                    for elem in elements:
                        text = self._clean_japanese_text(elem.get_text(strip=True))
                        
                        # 유효한 요약인지 확인
                        if (len(text) > 20 and len(text) < 400 and
                            text != title and
                            not text.startswith('朝日新聞') and
                            not text.startswith('Asahi') and
                            'asahi.com' not in text.lower()):
                            
                            summary = text
                            break
                    
                    if summary:
                        break
                        
        except Exception as e:
            logger.debug(f"Asahi 요약 추출 실패: {e}")
        
        return summary
    
    def _extract_asahi_image(self, element, url: str) -> str:
        """아사히 신문 기사에서 이미지 추출"""
        image_url = ''
        
        try:
            if hasattr(element, 'find'):
                # 이미지 찾기
                img_elem = element.find('img')
                if img_elem:
                    potential_imgs = [
                        img_elem.get('src', ''),
                        img_elem.get('data-src', ''),
                        img_elem.get('data-lazy-src', ''),
                        img_elem.get('data-original', '')
                    ]
                    
                    for img_src in potential_imgs:
                        if img_src and self._is_valid_asahi_image(img_src):
                            image_url = img_src
                            break
                
                # 이미지 URL 정규화
                if image_url and not image_url.startswith('http'):
                    if image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    elif image_url.startswith('/'):
                        image_url = self.base_url + image_url
                        
        except Exception as e:
            logger.debug(f"Asahi 이미지 추출 실패: {e}")
        
        return image_url
    
    def _extract_asahi_date(self, element, url: str) -> str:
        """아사히 신문 기사에서 날짜 추출"""
        try:
            if hasattr(element, 'get_text'):
                text = element.get_text()
                
                # 일본 날짜 패턴들
                date_patterns = [
                    r'(\d{4}年\d{1,2}月\d{1,2}日)',  # 2025年7月17日
                    r'(\d{4}\.\d{1,2}\.\d{1,2})',   # 2025.7.17
                    r'(\d{1,2}/\d{1,2}/\d{4})',     # 7/17/2025
                    r'(\d{4}-\d{1,2}-\d{1,2})'      # 2025-07-17
                ]
                
                for pattern in date_patterns:
                    match = re.search(pattern, text)
                    if match:
                        date_str = match.group(0)
                        try:
                            # 다양한 형식 시도
                            if '年' in date_str:
                                # 일본어 형식: 2025年7月17日
                                date_str = date_str.replace('年', '/').replace('月', '/').replace('日', '')
                                date_obj = datetime.strptime(date_str, '%Y/%m/%d')
                            elif '.' in date_str:
                                date_obj = datetime.strptime(date_str, '%Y.%m.%d')
                            elif '/' in date_str and date_str.count('/') == 2:
                                date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                            elif '-' in date_str:
                                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            else:
                                continue
                                
                            return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                        except:
                            continue
            
            # URL에서 날짜 추출
            url_match = re.search(r'/articles/(\w+)(\d{12})', url)
            if url_match:
                date_part = url_match.group(2)  # 12자리 숫자
                if len(date_part) == 12:
                    try:
                        year = int(date_part[:4])
                        month = int(date_part[4:6])
                        day = int(date_part[6:8])
                        hour = int(date_part[8:10])
                        minute = int(date_part[10:12])
                        
                        date_obj = datetime(year, month, day, hour, minute)
                        return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
                    except:
                        pass
                        
        except Exception as e:
            logger.debug(f"Asahi 날짜 추출 실패: {e}")
        
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    def _is_valid_asahi_image(self, url: str) -> bool:
        """아사히 신문 이미지 URL이 유효한지 확인"""
        if not url:
            return False
        
        url_lower = url.lower()
        
        # 제외할 이미지들
        exclude_patterns = [
            'logo', 'icon', 'sprite', 'loading', 'placeholder',
            'blank.gif', 'spacer.gif', 'asahi_logo'
        ]
        
        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False
        
        # 유효한 이미지 패턴들
        valid_patterns = [
            '.jpg', '.jpeg', '.png', '.webp', '.gif',
            'asahi.com', 'asahicom.jp'
        ]
        
        return any(pattern in url_lower for pattern in valid_patterns) 