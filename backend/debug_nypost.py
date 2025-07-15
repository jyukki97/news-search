# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import sys
sys.path.append('/app')

def debug_nypost_extraction():
    """NY Post 추출 과정 상세 디버깅"""
    print("=== NY Post 추출 과정 디버깅 ===")
    
    url = "https://nypost.com/search"
    params = {'q': 'technology'}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 실제 기사 링크들 분석
        article_links = soup.select('a[href*="/20"]')
        print(f"발견된 기사 링크 수: {len(article_links)}")
        
        processed_count = 0
        valid_count = 0
        
        for i, link in enumerate(article_links[:10]):  # 처음 10개만 분석
            processed_count += 1
            print(f"\n--- 링크 {i+1} 분석 ---")
            
            url = link.get('href', '')
            print(f"URL: {url}")
            
            if not url:
                print("❌ URL 없음")
                continue
            
            if 'nypost.com' not in url:
                print("❌ NY Post URL 아님")
                continue
                
            title = link.get_text(strip=True)
            print(f"기본 제목: '{title}'")
            
            # 부모 요소 찾기
            parent = link.find_parent(['div', 'article'])
            print(f"부모 요소: {parent.name if parent else 'None'}")
            
            if parent:
                # story 컨테이너 찾기
                story_container = parent.find_parent(class_=lambda x: x and 'story' in x) or parent
                print(f"Story 컨테이너: {story_container.name if story_container else 'None'}")
                
                if story_container:
                    # 제목 후보들 찾기
                    h3 = story_container.find('h3')
                    h2 = story_container.find('h2')
                    h4 = story_container.find('h4')
                    
                    print(f"H3: '{h3.get_text(strip=True) if h3 else 'None'}'")
                    print(f"H2: '{h2.get_text(strip=True) if h2 else 'None'}'")
                    print(f"H4: '{h4.get_text(strip=True) if h4 else 'None'}'")
                    
                    # 더 나은 제목 찾기
                    for candidate in [h3, h2, h4]:
                        if candidate:
                            candidate_text = candidate.get_text(strip=True)
                            if len(candidate_text) > len(title) and len(candidate_text) > 10:
                                title = candidate_text
                                print(f"✅ 개선된 제목: '{title}'")
                                break
            
            print(f"최종 제목: '{title}'")
            print(f"제목 길이: {len(title)}")
            
            if len(title) >= 10:
                valid_count += 1
                print("✅ 유효한 기사")
            else:
                print("❌ 제목이 너무 짧음")
        
        print(f"\n=== 요약 ===")
        print(f"처리된 링크: {processed_count}")
        print(f"유효한 기사: {valid_count}")
        
    except Exception as e:
        print(f"분석 실패: {e}")
        import traceback
        traceback.print_exc()

def analyze_nypost_search():
    """NY Post 검색 페이지 구조 분석"""
    print("=== NY Post 검색 페이지 분석 ===")
    
    url = "https://nypost.com/search"
    params = {'q': 'technology'}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        print(f"응답 상태: {response.status_code}")
        print(f"최종 URL: {response.url}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 페이지 제목 확인
            title = soup.find('title')
            print(f"페이지 제목: {title.get_text() if title else 'None'}")
            
            # 검색 결과가 실제로 나왔는지 확인
            results_text = soup.get_text()
            if 'technology' in results_text.lower():
                print("✅ 검색어가 페이지에 포함됨")
            else:
                print("❌ 검색어가 페이지에 없음")
            
            # 기사 링크 패턴 확인
            article_links = soup.select('a[href*="/20"]')
            print(f"기사 링크 수: {len(article_links)}")
            
            # 처음 3개 링크 상세 분석
            for i, link in enumerate(article_links[:3]):
                print(f"\n링크 {i+1}:")
                print(f"  href: {link.get('href', '')}")
                print(f"  text: {link.get_text(strip=True)}")
                print(f"  parent: {link.parent.name if link.parent else 'None'}")
                
    except Exception as e:
        print(f"분석 실패: {e}")
        import traceback
        traceback.print_exc()

def test_nypost():
    """NY Post 스크래퍼 테스트"""
    print("\n=== NY Post 스크래퍼 테스트 ===")
    
    from app.scrapers.nypost_scraper import NYPostScraper
    
    scraper = NYPostScraper()
    
    try:
        results = scraper.search_news("technology", 3)
        print(f"결과 수: {len(results)}")
        
        for i, article in enumerate(results, 1):
            print(f"\n{i}. {article['title']}")
            print(f"   URL: {article['url']}")
            print(f"   요약: {article['summary'][:100]}...")
            print(f"   이미지: {article['image_url']}")
            print(f"   날짜: {article['published_date']}")
    
    except Exception as e:
        print(f"에러: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_nypost_search()
    debug_nypost_extraction()
    test_nypost() 