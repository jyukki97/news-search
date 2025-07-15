from fastapi import APIRouter, Query, HTTPException
from typing import List, Dict
import logging
import asyncio
import concurrent.futures

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

@router.get("/search")
async def search_news(
    query: str = Query(..., description="검색할 키워드"),
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    per_site_limit: int = Query(3, ge=1, le=10, description="사이트당 가져올 기사 수 (1-10)"),
    sources: str = Query("all", description="검색할 사이트 (all, bbc, thesun, nypost, dailymail, scmp, vnexpress, bangkokpost, asahi, yomiuri 중 콤마로 구분)"),
    sort: str = Query("date_desc", description="정렬 방식 (date_desc: 최신순, date_asc: 과거순, relevance: 관련도순)")
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

@router.get("/categories")
async def get_categories() -> Dict:
    """사용 가능한 뉴스 카테고리 목록"""
    return {
        "success": True,
        "categories": ["top_stories", "world", "uk", "business", "technology", "science", "health", "sports", "politics", "entertainment"],
        "descriptions": {
            "top_stories": "주요 뉴스",
            "world": "국제 뉴스", 
            "uk": "영국 뉴스",
            "business": "비즈니스",
            "technology": "기술",
            "science": "과학/환경",
            "health": "건강",
            "sports": "스포츠",
            "politics": "정치",
            "entertainment": "연예/오락"
        }
    } 