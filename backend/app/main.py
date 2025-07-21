from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from .api.news_router import router as news_router

app = FastAPI(
    title="News Search API",
    description="여러 뉴스 사이트를 검색하는 API",
    version="1.0.0"
)

# CORS 설정 (프론트엔드 연동용) - Render 배포 지원
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3006")
if cors_origins == "*":
    allowed_origins = ["*"]
else:
    allowed_origins = [origin.strip() for origin in cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 뉴스 API 라우터 추가
app.include_router(news_router)

@app.get("/")
@app.head("/")  # Render health check를 위한 HEAD 메서드 지원
async def root():
    return {"message": "News Search API가 실행 중입니다!"}

@app.get("/health")
@app.head("/health")  # health check용 HEAD 메서드 지원
async def health_check():
    return {"status": "healthy", "service": "news-search-backend"} 