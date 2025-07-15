#!/usr/bin/env python3
"""BBC 스크래퍼 테스트 스크립트"""

import sys
import os
import logging

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.scrapers.bbc_scraper import BBCNewsScraper

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_bbc_scraper():
    """BBC 스크래퍼 테스트"""
    scraper = BBCNewsScraper()
    
    # 테스트 검색어
    test_queries = ["climate change", "technology", "sports"]
    
    for query in test_queries:
        print(f"\n{'='*50}")
        print(f"검색어: {query}")
        print(f"{'='*50}")
        
        articles = scraper.search_news(query, limit=3)
        
        if articles:
            for i, article in enumerate(articles, 1):
                print(f"\n{i}. {article['title']}")
                print(f"   URL: {article['url']}")
                print(f"   요약: {article['summary'][:100]}..." if article['summary'] else "   요약: 없음")
                print(f"   날짜: {article['published_date']}")
        else:
            print("검색 결과가 없습니다.")

if __name__ == "__main__":
    test_bbc_scraper() 