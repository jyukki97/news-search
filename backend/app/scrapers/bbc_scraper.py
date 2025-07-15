#!/usr/bin/env python3
# coding: utf-8

import requests
from bs4 import BeautifulSoup
from typing import List, Dict
import logging
from datetime import datetime

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
            
            selectors = [
                'h2, h3, h4',
                'a[href*="/news/"]',
                'a[href*="/sport/"]'
            ]
            
            found_items = set()
            
            for selector in selectors:
                elements = soup.select(selector)
                
                for element in elements:
                    try:
                        title = ''
                        url = ''
                        summary = ''
                        image_url = ''
                        
                        if element.name in ['h2', 'h3', 'h4']:
                            title = element.get_text(strip=True)
                            
                            link_elem = element.find('a')
                            if not link_elem:
                                parent = element.find_parent(['div', 'article'])
                                if parent:
                                    link_elem = parent.find('a')
                            
                            if link_elem:
                                url = link_elem.get('href', '')
                        
                        elif element.name == 'a':
                            url = element.get('href', '')
                            title = element.get_text(strip=True)
                            
                            parent = element.find_parent(['div', 'article'])
                            if parent:
                                title_elem = parent.find(['h2', 'h3', 'h4'])
                                if title_elem and len(title_elem.get_text(strip=True)) > len(title):
                                    title = title_elem.get_text(strip=True)
                                
                                desc_elem = parent.find('p')
                                if desc_elem:
                                    summary = desc_elem.get_text(strip=True)
                        
                        if not title or not url or len(title) < 5:
                            continue
                        
                        if url.startswith('/'):
                            url = self.base_url + url
                        elif not url.startswith('http'):
                            continue
                        
                        if 'bbc.com' not in url:
                            continue
                        
                        parent = element.find_parent(['div', 'article', 'section'])
                        if parent:
                            img_elem = parent.find('img')
                            if img_elem:
                                image_url = (img_elem.get('src', '') or 
                                            img_elem.get('data-src', '') or 
                                            img_elem.get('data-lazy-src', ''))
                        
                        if image_url and not image_url.startswith('http'):
                            if image_url.startswith('//'):
                                image_url = 'https:' + image_url
                            elif image_url.startswith('/'):
                                image_url = self.base_url + image_url
                        
                        item_key = (title, url)
                        if item_key in found_items:
                            continue
                        found_items.add(item_key)
                        
                        article = {
                            'title': title,
                            'url': url,
                            'summary': summary[:300] if summary else '',
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
                        logger.debug("BBC element parsing failed: {}".format(e))
                        continue
                
                if len(articles) >= limit:
                    break
                    
        except Exception as e:
            logger.error("BBC HTML parsing failed: {}".format(e))
        
        return articles[:limit]
    
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