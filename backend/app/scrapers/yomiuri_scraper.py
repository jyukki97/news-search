# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import logging
from datetime import datetime, timedelta
import json
import re
import time
from urllib.parse import quote # Added missing import

logger = logging.getLogger(__name__)

class YomiuriScraper:
    """Yomiuri Shimbun 뉴스 스크래퍼 (www.yomiuri.co.jp)"""
    
    def __init__(self):
        self.base_url = "https://www.yomiuri.co.jp"
        self.english_url = "https://www.yomiuri.co.jp/english"  # English section
        self.search_url = "https://www.yomiuri.co.jp/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
    def search_news(self, query: str, limit: int = 10) -> List[Dict]:
        """Yomiuri Shimbun에서 뉴스 검색"""
        try:
            logger.info(f"Yomiuri Shimbun 검색: {query}")
            
            # 실제 Yomiuri 검색 API URL 사용
            search_url = f"https://www.yomiuri.co.jp/web-search/?st=1&wo={quote(query)}&ac=srch&ar=1&fy=&fm=&fd=&ty=&tm=&td="
            
            logger.info(f"Yomiuri 검색 시도: {search_url}")
            response = requests.get(search_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            articles = self._extract_search_results(response.text, limit, query)
            if articles:
                logger.info(f"Yomiuri에서 {len(articles)}개 기사 발견")
                return articles
            else:
                logger.debug("Yomiuri 검색 결과 없음")
                
                # 검색 실패 시 영어 섹션 최신 뉴스로 대체
                logger.info("Yomiuri 검색 실패, 최신 뉴스로 대체")
                return self.get_latest_news('news', limit)
            
        except Exception as e:
            logger.error(f"Yomiuri 검색 실패: {e}")
            # 오류 시에도 최신 뉴스로 폴백
            return self.get_latest_news('news', limit)
    
    def _extract_search_results(self, html_content: str, limit: int, query: str = '') -> List[Dict]:
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
                    
                logger.debug(f"Yomiuri {selector}: {len(elements)}개 요소 발견")
                
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
                        logger.debug(f"Yomiuri 기사 파싱 실패: {e}")
                        continue
                
                if len(articles) >= limit:
                    break
                    
        except Exception as e:
            logger.error(f"Yomiuri HTML 파싱 실패: {e}")
        
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
            logger.debug(f"Yomiuri 날짜 추출 실패: {e}")
        
        # 기본값: 현재 시간
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    def _extract_category_from_url(self, url: str) -> str:
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
            elif '/english/' in url:  # English section
                return 'japan'
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
    
    def get_latest_news(self, category: str = 'news', limit: int = 10) -> List[Dict]:
        """Yomiuri Shimbun 최신 뉴스 가져오기"""
        try:
            # 카테고리별 URL 매핑 (일본어 메인 사이트 사용)
            category_urls = {
                'all': 'https://www.yomiuri.co.jp',  # 메인 홈페이지
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
            
            url = category_urls.get(category, category_urls['news'])
            
            logger.info(f"Yomiuri 최신 뉴스 가져오기: {url}")
            
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            articles = self._extract_search_results(response.text, limit)
            logger.info(f"Yomiuri 최신 뉴스 {len(articles)}개 수집")
            
            # 결과가 없거나 적으면 search_news로 fallback
            if not articles or len(articles) < limit // 2:
                logger.info("Yomiuri 최신 뉴스 결과 부족, 검색으로 fallback")
                return self.search_news('breaking news', limit)
            
            return articles
            
        except Exception as e:
            logger.error(f"Yomiuri 최신 뉴스 가져오기 실패: {e}")
            # 404나 다른 오류 시 search_news로 fallback
            logger.info("Yomiuri 최신 뉴스 실패, 검색으로 fallback")
            try:
                return self.search_news('breaking news', limit)
            except Exception as fallback_error:
                logger.error(f"Yomiuri fallback 검색도 실패: {fallback_error}")
                return [] 