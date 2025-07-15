from fastapi import APIRouter, Query, HTTPException
from typing import List, Dict, Optional
import logging
import asyncio
import concurrent.futures
from datetime import datetime, timedelta
import re

from ..scrapers.bbc_scraper import BBCNewsScraper
from ..scrapers.nypost_scraper import NYPostScraper
from ..scrapers.thesun_scraper import TheSunScraper
from ..scrapers.dailymail_scraper import DailyMailScraper
from ..scrapers.scmp_scraper import SCMPScraper
from ..scrapers.vnexpress_scraper import VNExpressScraper
from ..scrapers.bangkokpost_scraper import BangkokPostScraper
from ..scrapers.asahi_scraper import AsahiScraper
from ..scrapers.yomiuri_scraper import YomiuriScraper

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/news", tags=["news"])

# 스크래퍼 인스턴스 생성
bbc_scraper = BBCNewsScraper()
nypost_scraper = NYPostScraper()
thesun_scraper = TheSunScraper()
vnexpress_scraper = VNExpressScraper()
bangkokpost_scraper = BangkokPostScraper()
asahi_scraper = AsahiScraper()
yomiuri_scraper = YomiuriScraper()
dailymail_scraper = DailyMailScraper()
scmp_scraper = SCMPScraper()

def run_scraper_search(scraper, query, limit):
    """스크래퍼 검색을 실행하는 헬퍼 함수"""
    try:
        return scraper.search_news(query, limit)
    except Exception as e:
        logger.error(f"{scraper.__class__.__name__} 검색 실패: {e}")
        return []

def filter_articles_by_date(articles: List[Dict], date_from: Optional[str], date_to: Optional[str]) -> List[Dict]:
    """날짜 범위로 기사 필터링"""
    if not date_from and not date_to:
        return articles
    
    filtered_articles = []
    
    for article in articles:
        try:
            published_date = article.get('published_date', '')
            if not published_date:
                # 날짜 정보가 없는 기사는 포함 (또는 제외할 수도 있음)
                filtered_articles.append(article)
                continue
            
            # 다양한 날짜 형식 파싱 시도
            article_date = parse_article_date(published_date)
            if not article_date:
                # 파싱 실패한 기사는 포함
                filtered_articles.append(article)
                continue
            
            # 날짜 범위 체크
            date_in_range = True
            
            if date_from:
                try:
                    from_date = datetime.strptime(date_from, '%Y-%m-%d')
                    if article_date < from_date:
                        date_in_range = False
                except:
                    pass  # date_from 파싱 실패시 무시
            
            if date_to and date_in_range:
                try:
                    to_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)  # 하루 끝까지 포함
                    if article_date >= to_date:
                        date_in_range = False
                except:
                    pass  # date_to 파싱 실패시 무시
            
            if date_in_range:
                filtered_articles.append(article)
                
        except Exception as e:
            logger.debug(f"날짜 필터링 중 오류: {e}")
            # 오류 발생시 해당 기사는 포함
            filtered_articles.append(article)
    
    return filtered_articles

def parse_article_date(date_string: str) -> Optional[datetime]:
    """다양한 날짜 형식을 파싱"""
    if not date_string:
        return None
    
    # 일반적인 날짜 형식들
    date_formats = [
        '%Y-%m-%d',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%a, %d %b %Y %H:%M:%S GMT',
        '%d %b %Y',
        '%B %d, %Y',
        '%d %B %Y',
        '%m/%d/%Y',
        '%d/%m/%Y'
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(date_string, fmt)
        except:
            continue
    
    # 정규식으로 날짜 패턴 추출 시도
    date_patterns = [
        r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
        r'(\d{1,2})/(\d{1,2})/(\d{4})',  # MM/DD/YYYY 또는 DD/MM/YYYY
        r'(\w+)\s+(\d{1,2}),?\s+(\d{4})',  # Month DD, YYYY
        r'(\d{1,2})\s+(\w+)\s+(\d{4})',   # DD Month YYYY
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, date_string)
        if match:
            try:
                groups = match.groups()
                if len(groups) == 3:
                    # 첫 번째 패턴 (YYYY-MM-DD)
                    if pattern == r'(\d{4})-(\d{1,2})-(\d{1,2})':
                        year, month, day = groups
                        return datetime(int(year), int(month), int(day))
                    # 다른 패턴들은 더 복잡한 처리가 필요할 수 있음
            except:
                continue
    
    return None

@router.get("/search")
async def search_news(
    query: str = Query(..., description="검색할 키워드"),
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    per_site_limit: int = Query(3, ge=1, le=10, description="사이트당 가져올 기사 수 (1-10)"),
    sources: str = Query("all", description="검색할 사이트 (all, bbc, thesun, nypost, dailymail, scmp, vnexpress, bangkokpost, asahi, yomiuri 중 콤마로 구분)"),
    sort: str = Query("date_desc", description="정렬 방식 (date_desc: 최신순, date_asc: 과거순, relevance: 관련도순)"),
    date_from: Optional[str] = Query(None, description="시작 날짜 (YYYY-MM-DD 형식)"),
    date_to: Optional[str] = Query(None, description="종료 날짜 (YYYY-MM-DD 형식)")
) -> Dict:
    """뉴스 통합 검색 (사이트별 페이지네이션)"""
    try:
        logger.info(f"뉴스 통합 검색 요청: {query}, 페이지: {page}, 사이트당: {per_site_limit}개, 사이트: {sources}")
        
        # 검색할 사이트 파싱
        requested_sources = [s.strip().lower() for s in sources.split(",")] if sources != "all" else ["all"]
        
        # 각 사이트에서 페이지별로 가져올 기사 수 계산
        # 페이지네이션을 위해 더 많이 가져온 후 필요한 부분만 추출
        fetch_limit = page * per_site_limit
        
        # 병렬로 여러 사이트에서 검색
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            # 각 스크래퍼별로 Future 생성 (필터링 적용)
            futures = {}
            
            if sources == "all" or "bbc" in requested_sources:
                futures[executor.submit(run_scraper_search, bbc_scraper, query, fetch_limit)] = "BBC News"
            if sources == "all" or "vnexpress" in requested_sources:
                futures[executor.submit(run_scraper_search, vnexpress_scraper, query, fetch_limit)] = "VN Express"
            if sources == "all" or "bangkokpost" in requested_sources:
                futures[executor.submit(run_scraper_search, bangkokpost_scraper, query, fetch_limit)] = "Bangkok Post"
            if sources == "all" or "asahi" in requested_sources:
                futures[executor.submit(run_scraper_search, asahi_scraper, query, fetch_limit)] = "Asahi Shimbun"
            if sources == "all" or "yomiuri" in requested_sources:
                futures[executor.submit(run_scraper_search, yomiuri_scraper, query, fetch_limit)] = "Yomiuri Shimbun"
            if sources == "all" or "thesun" in requested_sources:
                futures[executor.submit(run_scraper_search, thesun_scraper, query, fetch_limit)] = "The Sun"
            if sources == "all" or "nypost" in requested_sources:
                futures[executor.submit(run_scraper_search, nypost_scraper, query, fetch_limit)] = "NY Post"
            if sources == "all" or "dailymail" in requested_sources:
                futures[executor.submit(run_scraper_search, dailymail_scraper, query, fetch_limit)] = "Daily Mail"
            if sources == "all" or "scmp" in requested_sources:
                futures[executor.submit(run_scraper_search, scmp_scraper, query, fetch_limit)] = "SCMP"
            
            # 결과 수집
            all_articles = []
            active_sources = []
            
            for future in concurrent.futures.as_completed(futures):
                source_name = futures[future]
                try:
                    articles = future.result()
                    if articles:
                        # 페이지네이션 적용: 해당 페이지에 해당하는 기사만 추출
                        start_idx = (page - 1) * per_site_limit
                        end_idx = start_idx + per_site_limit
                        page_articles = articles[start_idx:end_idx]
                        
                        if page_articles:
                            all_articles.extend(page_articles)
                            active_sources.append(source_name)
                            logger.info(f"{source_name}에서 페이지 {page}: {len(page_articles)}개 기사 수집")
                except Exception as e:
                    logger.error(f"{source_name} 검색 실패: {e}")
        
        # 정렬 적용
        if all_articles:
            if sort == "date_desc":
                # 날짜 순으로 정렬 (최신순)
                all_articles.sort(key=lambda x: x.get('published_date', ''), reverse=True)
            elif sort == "date_asc":
                # 날짜 순으로 정렬 (과거순)
                all_articles.sort(key=lambda x: x.get('published_date', ''), reverse=False)
            elif sort == "relevance":
                # 관련도 순으로 정렬
                all_articles.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        # 날짜 범위 필터링 적용
        if date_from or date_to:
            all_articles = filter_articles_by_date(all_articles, date_from, date_to)
            logger.info(f"날짜 범위 필터링 적용: 시작={date_from}, 종료={date_to}, 필터링 후 기사 수: {len(all_articles)}")
        
        # 다음 페이지 여부 확인 (간단히 현재 페이지에서 기사가 있다면 다음 페이지도 있을 가능성이 있다고 가정)
        has_next_page = len(all_articles) > 0
        
        return {
            "success": True,
            "query": query,
            "page": page,
            "per_site_limit": per_site_limit,
            "total_articles": len(all_articles),
            "active_sources": active_sources,
            "has_next_page": has_next_page,
            "articles": all_articles
        }
        
    except Exception as e:
        logger.error(f"뉴스 검색 실패: {e}")
        raise HTTPException(status_code=500, detail=f"검색 중 오류 발생: {str(e)}")

@router.get("/latest")
async def get_latest_news(
    category: str = Query("top_stories", description="뉴스 카테고리"),
    limit: int = Query(10, ge=1, le=50, description="가져올 기사 수"),
    source: str = Query("all", description="뉴스 소스 (all, bbc, nypost, thesun, dailymail, scmp, vnexpress, bangkokpost, asahi, yomiuri)")
) -> Dict:
    """카테고리별 최신 뉴스"""
    try:
        logger.info(f"최신 뉴스 요청: {category}, 소스: {source}")
        
        all_articles = []
        sources = []
        
        if source == "all" or source == "bbc":
            try:
                bbc_articles = bbc_scraper.get_latest_news(category, limit)
                if bbc_articles:
                    all_articles.extend(bbc_articles)
                    sources.append("BBC News")
            except Exception as e:
                logger.error(f"BBC 최신 뉴스 실패: {e}")
        
        if source == "all" or source == "nypost":
            try:
                nypost_articles = nypost_scraper.get_latest_news(category, limit)
                if nypost_articles:
                    all_articles.extend(nypost_articles)
                    sources.append("NY Post")
            except Exception as e:
                logger.error(f"NY Post 최신 뉴스 실패: {e}")
        
        if source == "all" or source == "thesun":
            try:
                thesun_articles = thesun_scraper.get_latest_news(category, limit)
                if thesun_articles:
                    all_articles.extend(thesun_articles)
                    sources.append("The Sun")
            except Exception as e:
                logger.error(f"The Sun 최신 뉴스 실패: {e}")
        
        if source == "all" or source == "dailymail":
            try:
                dailymail_articles = dailymail_scraper.get_latest_news(category, limit)
                if dailymail_articles:
                    all_articles.extend(dailymail_articles)
                    sources.append("Daily Mail")
            except Exception as e:
                logger.error(f"Daily Mail 최신 뉴스 실패: {e}")
        
        if source == "all" or source == "scmp":
            try:
                scmp_articles = scmp_scraper.get_latest_news(category, limit)
                if scmp_articles:
                    all_articles.extend(scmp_articles)
                    sources.append("SCMP")
            except Exception as e:
                logger.error(f"SCMP 최신 뉴스 실패: {e}")
        
        if source == "all" or source == "vnexpress":
            try:
                vnexpress_articles = vnexpress_scraper.get_latest_news(category, limit)
                if vnexpress_articles:
                    all_articles.extend(vnexpress_articles)
                    sources.append("VN Express")
            except Exception as e:
                logger.error(f"VN Express 최신 뉴스 실패: {e}")
        
        if source == "all" or source == "bangkokpost":
            try:
                bangkokpost_articles = bangkokpost_scraper.get_latest_news(category, limit)
                if bangkokpost_articles:
                    all_articles.extend(bangkokpost_articles)
                    sources.append("Bangkok Post")
            except Exception as e:
                logger.error(f"Bangkok Post 최신 뉴스 실패: {e}")
        
        if source == "all" or source == "asahi":
            try:
                asahi_articles = asahi_scraper.get_latest_news(category, limit)
                if asahi_articles:
                    all_articles.extend(asahi_articles)
                    sources.append("Asahi Shimbun")
            except Exception as e:
                logger.error(f"Asahi Shimbun 최신 뉴스 실패: {e}")
        
        if source == "all" or source == "yomiuri":
            try:
                yomiuri_articles = yomiuri_scraper.get_latest_news(category, limit)
                if yomiuri_articles:
                    all_articles.extend(yomiuri_articles)
                    sources.append("Yomiuri Shimbun")
            except Exception as e:
                logger.error(f"Yomiuri Shimbun 최신 뉴스 실패: {e}")
        
        # 날짜 순으로 정렬
        if all_articles:
            all_articles.sort(key=lambda x: x.get('published_date', ''), reverse=True)
            all_articles = all_articles[:limit]
        
        return {
            "success": True,
            "category": category,
            "total_articles": len(all_articles),
            "sources": sources,
            "articles": all_articles
        }
        
    except Exception as e:
        logger.error(f"최신 뉴스 가져오기 실패: {e}")
        raise HTTPException(status_code=500, detail=f"최신 뉴스 가져오기 실패: {str(e)}")

@router.get("/trending")
async def get_trending_news(
    category: str = Query("all", description="카테고리 (all, news, sports, business, technology, entertainment)"),
    limit: int = Query(5, ge=1, le=20, description="사이트당 가져올 기사 수 (1-20)"),
    sources: str = Query("all", description="검색할 사이트 (all, bbc, thesun, nypost, dailymail, scmp, vnexpress, bangkokpost, asahi, yomiuri 중 콤마로 구분)")
) -> Dict:
    """각 사이트별 인기/트렌딩 뉴스 가져오기"""
    try:
        logger.info(f"트렌딩 뉴스 요청: 카테고리={category}, 사이트당={limit}개, 사이트={sources}")
        
        # 검색할 사이트 파싱
        requested_sources = [s.strip().lower() for s in sources.split(",")] if sources != "all" else ["all"]
        
        # 카테고리별 키워드 매핑
        category_keywords = {
            "all": "breaking news",
            "news": "breaking news",
            "sports": "sports",
            "business": "business economy",
            "technology": "technology tech",
            "entertainment": "entertainment celebrity",
            "health": "health",
            "world": "world international"
        }
        
        search_keyword = category_keywords.get(category.lower(), "breaking news")
        
        # 병렬로 여러 사이트에서 트렌딩 뉴스 가져오기
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {}
            
            if sources == "all" or "bbc" in requested_sources:
                futures[executor.submit(run_scraper_search, bbc_scraper, search_keyword, limit)] = "BBC News"
            if sources == "all" or "vnexpress" in requested_sources:
                futures[executor.submit(run_scraper_search, vnexpress_scraper, search_keyword, limit)] = "VN Express"
            if sources == "all" or "bangkokpost" in requested_sources:
                futures[executor.submit(run_scraper_search, bangkokpost_scraper, search_keyword, limit)] = "Bangkok Post"
            if sources == "all" or "asahi" in requested_sources:
                futures[executor.submit(run_scraper_search, asahi_scraper, search_keyword, limit)] = "Asahi Shimbun"
            if sources == "all" or "yomiuri" in requested_sources:
                futures[executor.submit(run_scraper_search, yomiuri_scraper, search_keyword, limit)] = "Yomiuri Shimbun"
            if sources == "all" or "thesun" in requested_sources:
                futures[executor.submit(run_scraper_search, thesun_scraper, search_keyword, limit)] = "The Sun"
            if sources == "all" or "nypost" in requested_sources:
                futures[executor.submit(run_scraper_search, nypost_scraper, search_keyword, limit)] = "NY Post"
            if sources == "all" or "dailymail" in requested_sources:
                futures[executor.submit(run_scraper_search, dailymail_scraper, search_keyword, limit)] = "Daily Mail"
            if sources == "all" or "scmp" in requested_sources:
                futures[executor.submit(run_scraper_search, scmp_scraper, search_keyword, limit)] = "SCMP"
            
            # 결과 수집 (사이트별로 분리)
            trending_by_source = {}
            active_sources = []
            total_articles = 0
            
            for future in concurrent.futures.as_completed(futures):
                source_name = futures[future]
                try:
                    articles = future.result()
                    if articles:
                        # 카테고리 필터링 (해당하는 경우)
                        if category.lower() != "all":
                            filtered_articles = []
                            for article in articles:
                                article_category = article.get('category', '').lower()
                                if category.lower() in article_category or category.lower() == article_category:
                                    filtered_articles.append(article)
                            articles = filtered_articles if filtered_articles else articles[:limit//2]  # 카테고리 매치가 없으면 일부만
                        
                        trending_by_source[source_name] = articles[:limit]
                        active_sources.append(source_name)
                        total_articles += len(articles[:limit])
                        logger.info(f"{source_name}에서 {len(articles[:limit])}개 트렌딩 뉴스 수집")
                except Exception as e:
                    logger.error(f"{source_name} 트렌딩 뉴스 수집 실패: {e}")
        
        return {
            "success": True,
            "category": category,
            "total_articles": total_articles,
            "active_sources": active_sources,
            "trending_by_source": trending_by_source,
            "last_updated": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"트렌딩 뉴스 가져오기 실패: {e}")
        raise HTTPException(status_code=500, detail=f"트렌딩 뉴스 가져오기 실패: {str(e)}")

@router.get("/categories")
async def get_categories() -> Dict:
    """사용 가능한 카테고리 목록 반환"""
    categories = {
        "all": "전체 뉴스",
        "news": "일반 뉴스",
        "sports": "스포츠",
        "business": "비즈니스/경제", 
        "technology": "기술/IT",
        "entertainment": "엔터테인먼트",
        "health": "건강",
        "world": "국제"
    }
    
    return {
        "success": True,
        "categories": list(categories.keys()),
        "descriptions": categories
    } 