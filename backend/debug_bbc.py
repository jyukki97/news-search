#!/usr/bin/env python3
"""BBC 웹사이트 구조 디버깅 스크립트"""

import requests
from bs4 import BeautifulSoup
import logging

logging.basicConfig(level=logging.INFO)

def debug_bbc_search():
    """BBC 검색 페이지 구조 분석"""
    
    url = "https://www.bbc.com/search"
    params = {'q': 'technology'}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    try:
        print("BBC 검색 요청 중...")
        response = requests.get(url, params=params, headers=headers, timeout=10)
        print(f"응답 상태: {response.status_code}")
        print(f"응답 URL: {response.url}")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 페이지 제목 확인
        title = soup.find('title')
        print(f"페이지 제목: {title.get_text() if title else 'None'}")
        
        # 모든 링크 찾기
        all_links = soup.find_all('a', href=True)
        print(f"전체 링크 수: {len(all_links)}")
        
        # BBC 뉴스 관련 링크 찾기
        news_links = []
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            if '/news/' in href or ('/sport/' in href and text):
                news_links.append({
                    'href': href,
                    'text': text[:100],
                    'classes': link.get('class', [])
                })
        
        print(f"\n뉴스 관련 링크 {len(news_links)}개 발견:")
        for i, link in enumerate(news_links[:10]):  # 상위 10개만 출력
            print(f"{i+1}. {link['text']}")
            print(f"   URL: {link['href']}")
            print(f"   클래스: {link['classes']}")
            print()
        
        # 검색 결과 컨테이너 찾기
        search_containers = soup.find_all(['div', 'article', 'section'], class_=True)
        print(f"\n클래스가 있는 컨테이너: {len(search_containers)}개")
        
        # 첫 번째 HTML 일부 출력
        print(f"\n응답 HTML (첫 1000자):")
        print(response.text[:1000])
        
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    debug_bbc_search() 