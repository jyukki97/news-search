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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/news", tags=["news"])

# 스크래퍼 인스턴스 생성
bbc_scraper = BBCNewsScraper()
nypost_scraper = NYPostScraper()
thesun_scraper = TheSunScraper()
vnexpress_scraper = VNExpressScraper()
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
    limit: int = Query(10, ge=1, le=50, description="가져올 기사 수 (1-50)")
) -> Dict:
    """뉴스 통합 검색"""
    try:
        logger.info(f"뉴스 통합 검색 요청: {query}")
        
        # 병렬로 여러 사이트에서 검색
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            # 각 스크래퍼별로 Future 생성
            futures = {
                executor.submit(run_scraper_search, bbc_scraper, query, limit): "BBC News",
                executor.submit(run_scraper_search, vnexpress_scraper, query, limit): "VN Express",
                # executor.submit(run_scraper_search, nypost_scraper, query, limit): "NY Post"  # 기술적 문제로 임시 비활성화
                # executor.submit(run_scraper_search, thesun_scraper, query, limit): "The Sun"  # 임시 비활성화
                # executor.submit(run_scraper_search, dailymail_scraper, query, limit): "Daily Mail"  # 임시 비활성화
                # executor.submit(run_scraper_search, scmp_scraper, query, limit): "SCMP"  # 임시 비활성화
            }
            
            # 결과 수집
            all_articles = []
            sources = []
            
            for future in concurrent.futures.as_completed(futures):
                source_name = futures[future]
                try:
                    articles = future.result()
                    if articles:
                        all_articles.extend(articles)
                        sources.append(source_name)
                        logger.info(f"{source_name}에서 {len(articles)}개 기사 수집")
                except Exception as e:
                    logger.error(f"{source_name} 검색 실패: {e}")
        
        # 결과가 너무 많으면 관련도와 날짜를 고려해서 정렬 후 제한
        if all_articles:
            # 날짜 순으로 정렬 (최신순)
            all_articles.sort(key=lambda x: x.get('published_date', ''), reverse=True)
            # 제한된 수만 반환
            all_articles = all_articles[:limit]
        
        return {
            "success": True,
            "query": query,
            "total_articles": len(all_articles),
            "sources": sources,
            "articles": all_articles
        }
        
    except Exception as e:
        logger.error(f"뉴스 검색 실패: {e}")
        raise HTTPException(status_code=500, detail=f"검색 중 오류 발생: {str(e)}")

@router.get("/latest")
async def get_latest_news(
    category: str = Query("top_stories", description="뉴스 카테고리"),
    limit: int = Query(10, ge=1, le=50, description="가져올 기사 수"),
    source: str = Query("all", description="뉴스 소스 (all, bbc, nypost, thesun, dailymail, scmp, vnexpress)")
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