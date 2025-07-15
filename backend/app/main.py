from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.news_router import router as news_router

app = FastAPI(
    title="News Search API",
    description="여러 뉴스 사이트를 검색하는 API",
    version="1.0.0"
)

# CORS 설정 (프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js 개발 서버
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 뉴스 API 라우터 추가
app.include_router(news_router)

@app.get("/")
async def root():
    return {"message": "News Search API가 실행 중입니다!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "news-search-backend"} 