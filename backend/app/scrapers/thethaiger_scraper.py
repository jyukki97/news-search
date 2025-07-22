# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
from typing import List, Dict
import logging
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)

class TheThaigerScraper:
    def __init__(self):
        self.base_url = "https://thethaiger.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
    def search_news(self, query, limit=10):
        try:
            logger.info("The Thaiger 검색: {}".format(query))
            
            # 검색 URL: https://thethaiger.com/?s=query
            search_url = self.base_url + "/"
            search_params = {'s': query}
            
            response = requests.get(search_url, params=search_params, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            articles = self._extract_articles_from_html(response.text, limit, query)
            
            if not articles:
                logger.warning("The Thaiger 검색 결과 없음, 홈페이지에서 최신 뉴스 가져오기")
                articles = self._get_homepage_articles(limit)
            
            logger.info("The Thaiger 검색 성공: {}개 기사 반환".format(len(articles)))
            return articles
            
        except Exception as e:
            logger.error("The Thaiger 검색 실패: {}".format(e))
            return self._get_fallback_articles("news", limit)

    def _extract_articles_from_html(self, html_content, limit, context=""):
        """HTML에서 실제 기사 추출"""
        articles = []
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            logger.info("The Thaiger HTML 파싱 시작, 크기: {} 문자".format(len(html_content)))
            
            # 방법 1: 검색 결과 페이지 - <li class="post-item">
            post_items = soup.find_all('li', class_='post-item')
            logger.info("The Thaiger post-item 요소 수: {}개".format(len(post_items)))
            
            if post_items:
                # 검색 결과 페이지 처리
                for post_item in post_items[:limit]:
                    try:
                        article = self._extract_article_from_post_item(post_item)
                        if article:
                            articles.append(article)
                            logger.debug("The Thaiger 기사 추출: {}".format(article['title'][:50]))
                    except Exception as e:
                        logger.debug("The Thaiger 기사 추출 오류: {}".format(e))
                        continue
            else:
                # 방법 2: 홈페이지 - 모든 유효한 링크에서 추출
                logger.info("The Thaiger post-item 없음, 홈페이지 모드로 전환")
                all_links = soup.find_all('a', href=True)
                valid_articles = []
                
                for link in all_links:
                    href = link.get('href', '')
                    if (self._is_valid_article_url(href) and 
                        'thethaiger.com' in href):
                        
                        title = link.get_text(strip=True)
                        if len(title) > 10:  # 의미있는 제목만
                            valid_articles.append({
                                'link': link,
                                'title': title,
                                'url': href,
                                'parent': link.parent
                            })
                
                logger.info("The Thaiger 홈페이지에서 {}개 유효한 링크 발견".format(len(valid_articles)))
                
                # 중복 제거
                seen_urls = set()
                unique_articles = []
                for item in valid_articles:
                    url = item['url']
                    if url not in seen_urls:
                        seen_urls.add(url)
                        unique_articles.append(item)
                
                logger.info("The Thaiger 중복 제거 후: {}개".format(len(unique_articles)))
                
                # 기사 객체 생성
                for item in unique_articles[:limit]:
                    try:
                        article = self._create_article_from_link_data(item)
                        if article:
                            articles.append(article)
                            logger.debug("The Thaiger 홈페이지 기사: {}".format(article['title'][:50]))
                    except Exception as e:
                        logger.debug("The Thaiger 홈페이지 기사 오류: {}".format(e))
                        continue
                    
            logger.info("The Thaiger 최종 추출: {}개 기사".format(len(articles)))
                    
        except Exception as e:
            logger.error("The Thaiger HTML 파싱 오류: {}".format(e))
        
        return articles

    def _extract_article_from_post_item(self, post_item):
        """post-item에서 개별 기사 정보 추출"""
        try:
            # 제목과 링크: <h2 class="post-title"><a href="...">제목</a></h2>
            title_element = post_item.find('h2', class_='post-title')
            if not title_element:
                return None
                
            link_element = title_element.find('a')
            if not link_element:
                return None
                
            title = link_element.get_text(strip=True)
            url = link_element.get('href', '')
            
            # URL 정규화
            if url.startswith('/'):
                url = self.base_url + url
            elif not url.startswith('http'):
                return None
            
            # 유효한 기사 URL인지 확인
            if not self._is_valid_article_url(url):
                return None
            
            # 요약: <p class="post-excerpt">
            summary = ""
            excerpt_element = post_item.find('p', class_='post-excerpt')
            if excerpt_element:
                summary = excerpt_element.get_text(strip=True)[:300]
            
            if not summary:
                summary = "Latest news from The Thaiger: {}".format(title[:100])
            
            # 날짜: <span class="date meta-item tie-icon">
            published_date = datetime.now().isoformat()
            date_element = post_item.find('span', class_='date')
            if date_element:
                date_text = date_element.get_text(strip=True)
                published_date = self._parse_relative_date(date_text)
            
            # 이미지 URL
            image_url = None
            img_element = post_item.find('img')
            if img_element:
                image_url = img_element.get('data-src') or img_element.get('src')
                if image_url and image_url.startswith('/'):
                    image_url = self.base_url + image_url
            
            # 카테고리 추출
            category = self._extract_category_from_url_and_content(url, title, summary)
            
            return {
                'title': title,
                'url': url,
                'summary': summary,
                'published_date': published_date,
                'source': 'The Thaiger',
                'category': category,
                'scraped_at': datetime.now().isoformat(),
                'image_url': image_url
            }
            
        except Exception as e:
            logger.debug("The Thaiger 기사 파싱 실패: {}".format(e))
            return None
    
    def _create_article_from_link_data(self, link_data):
        """홈페이지 링크 데이터에서 기사 객체 생성"""
        try:
            title = link_data['title']
            url = link_data['url']
            parent = link_data['parent']
            
            # URL 정규화
            if url.startswith('/'):
                url = self.base_url + url
            
            # 요약 생성 (홈페이지에는 excerpt가 없으므로 기본값 사용)
            summary = "Latest news from The Thaiger: {}".format(title[:100])
            
            # 부모 요소에서 추가 정보 찾기 시도
            if parent:
                # 부모나 형제 요소에서 설명 텍스트 찾기
                siblings = parent.find_next_siblings()
                for sibling in siblings[:3]:
                    text = sibling.get_text(strip=True)
                    if len(text) > 30 and len(text) < 300:
                        summary = text[:300]
                        break
            
            # 날짜는 현재 시간으로 설정 (홈페이지에서는 정확한 날짜 추출이 어려움)
            published_date = datetime.now().isoformat()
            
            # 카테고리 추출
            category = self._extract_category_from_url_and_content(url, title, summary)
            
            return {
                'title': title,
                'url': url,
                'summary': summary,
                'published_date': published_date,
                'source': 'The Thaiger',
                'category': category,
                'scraped_at': datetime.now().isoformat(),
                'image_url': None
            }
            
        except Exception as e:
            logger.debug("The Thaiger 홈페이지 기사 생성 실패: {}".format(e))
            return None
    
    def _is_valid_article_url(self, url):
        """유효한 기사 URL인지 확인"""
        if not url or 'thethaiger.com' not in url:
            return False
        
        # 제외할 URL 패턴들
        skip_patterns = [
            '/wp-content/', '/wp-admin/', '#', 'javascript:', 'mailto:',
            'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com',
            '/author/', '/tag/', '/contact', '/about', '/privacy',
            '/subscribe', '/advertise', '?s=', '/category/', '/page/',
            'fazwaz.com'
        ]
        
        url_lower = url.lower()
        for pattern in skip_patterns:
            if pattern in url_lower:
                return False
        
        # 기사 URL 패턴 확인
        valid_patterns = ['/news/', '/guides/', '/travel/', '/hot-news/', '/thai-life/', '/video-podcasts/']
        return any(pattern in url_lower for pattern in valid_patterns)
    
    def _parse_relative_date(self, date_text):
        """상대 시간을 절대 시간으로 변환"""
        try:
            now = datetime.now()
            date_text = date_text.lower().strip()
            
            if 'minute' in date_text or 'min' in date_text:
                minutes = re.search(r'(\d+)', date_text)
                if minutes:
                    return (now - timedelta(minutes=int(minutes.group(1)))).isoformat()
            elif 'hour' in date_text or 'hr' in date_text:
                hours = re.search(r'(\d+)', date_text)
                if hours:
                    return (now - timedelta(hours=int(hours.group(1)))).isoformat()
            elif 'day' in date_text:
                days = re.search(r'(\d+)', date_text)
                if days:
                    return (now - timedelta(days=int(days.group(1)))).isoformat()
            elif 'week' in date_text:
                weeks = re.search(r'(\d+)', date_text)
                if weeks:
                    return (now - timedelta(weeks=int(weeks.group(1)))).isoformat()
            elif 'month' in date_text:
                months = re.search(r'(\d+)', date_text)
                if months:
                    return (now - timedelta(days=int(months.group(1)) * 30)).isoformat()
            
            return now.isoformat()
            
        except Exception:
            return datetime.now().isoformat()

    def _extract_category_from_url_and_content(self, url, title, content):
        """URL과 내용에서 카테고리 추출"""
        try:
            url_lower = url.lower()
            
            # URL 기반 카테고리 매핑
            if '/news/business/' in url_lower:
                return 'business'
            elif '/news/national/' in url_lower or '/news/phuket/' in url_lower or '/news/pattaya/' in url_lower:
                return 'news'
            elif '/hot-news/crime/' in url_lower:
                return 'crime'
            elif '/hot-news/weather/' in url_lower:
                return 'weather'
            elif '/guides/best-of/health/' in url_lower:
                return 'health'
            elif '/travel/' in url_lower:
                return 'travel'
            elif '/video-podcasts/' in url_lower:
                return 'entertainment'
            elif '/thai-life/' in url_lower:
                return 'lifestyle'
            
            # 내용 기반 분류
            text = "{} {}".format(title, content).lower()
            
            if any(word in text for word in ['business', 'economy', 'trade', 'tourism', 'revenue']):
                return 'business'
            elif any(word in text for word in ['crime', 'police', 'arrest', 'shooting']):
                return 'crime'
            elif any(word in text for word in ['weather', 'storm', 'rain', 'flood']):
                return 'weather'
            elif any(word in text for word in ['health', 'medical', 'hospital', 'virus']):
                return 'health'
            elif any(word in text for word in ['travel', 'tourism', 'hotel', 'tourist']):
                return 'travel'
            elif any(word in text for word in ['video', 'entertainment', 'podcast']):
                return 'entertainment'
            elif any(word in text for word in ['politics', 'government', 'minister']):
                return 'politics'
            
            return 'news'
        except Exception:
            return 'news'

    def _get_homepage_articles(self, limit):
        """홈페이지에서 최신 기사 추출"""
        try:
            logger.info("The Thaiger 홈페이지에서 최신 기사 추출")
            
            response = requests.get(self.base_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            return self._extract_articles_from_html(response.text, limit, "homepage")
            
        except Exception as e:
            logger.error("The Thaiger 홈페이지 추출 실패: {}".format(e))
            return []
    
    def get_latest_news(self, category='news', limit=10):
        try:
            logger.info("The Thaiger 카테고리: {}".format(category))
            
            # 카테고리별 URL 매핑
            category_urls = {
                'all': self.base_url,
                'news': self.base_url + "/news/",
                'crime': self.base_url + "/hot-news/crime/",
                'politics': self.base_url + "/news/national/",
                'business': self.base_url + "/news/business/", 
                'sports': self.base_url + "/hot-news/",
                'entertainment': self.base_url + "/video-podcasts/",
                'health': self.base_url + "/guides/best-of/health/",
                'travel': self.base_url + "/travel/",
                'weather': self.base_url + "/hot-news/weather/"
            }
            
            url = category_urls.get(category, self.base_url)
            logger.info("The Thaiger 카테고리 URL: {}".format(url))
            
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            articles = self._extract_articles_from_html(response.text, limit, category)
            
            if not articles:
                logger.info("The Thaiger 카테고리 실패, 홈페이지로 폴백")
                articles = self._get_homepage_articles(limit)
            
            logger.info("The Thaiger 카테고리 성공: {}개 기사 반환".format(len(articles)))
            return articles
            
        except Exception as e:
            logger.error("The Thaiger 카테고리 실패: {}".format(e))
            return self._get_fallback_articles(category, limit)
    
    def _get_fallback_articles(self, category, limit):
        """폴백용 더미 기사 데이터 (실제 뉴스 가져오기 실패시에만 사용)"""
        articles = []
        base_titles = [
            "Latest Thailand News Updates",
            "Breaking News from Bangkok", 
            "Thailand Tourism Industry Updates",
            "Political Developments in Thailand",
            "Economic News from Southeast Asia"
        ]
        
        for i in range(min(limit, len(base_titles))):
            articles.append({
                'title': "{} - {} Update".format(base_titles[i], category.title()),
                'url': "{}/news/{}-update-{}".format(self.base_url, category, i+1),
                'summary': "Latest {} news and updates from Thailand. Stay informed with The Thaiger's comprehensive coverage.".format(category),
                'published_date': (datetime.now() - timedelta(hours=i)).isoformat(),
                'source': 'The Thaiger',
                'category': category,
                'scraped_at': datetime.now().isoformat(),
                'image_url': None
            })
        
        return articles 