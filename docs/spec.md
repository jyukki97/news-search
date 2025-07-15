# News Search Project

## 목적

* 여러 사이트에 있는 뉴스 기사를 한번에 검색하기 쉽게 만드는 사이트 (개인 용도)

## 검색 사이트
1. New York Post - https://nypost.com/
2. The Sun - https://www.thesun.co.uk/
3. Daily Mail - https://www.dailymail.co.uk/
4. 영국 BBC - https://www.bbc.com/
5. 사우스 차이나 모닝 포스트 - https://www.scmp.com/
6. VN 익스프레스 - https://e.vnexpress.net/
7. 방콕 포스트 - https://www.bangkokpost.com/
8. 아사히 신문 - https://www.asahi.com/
9. 요미우리 신문 - https://www.yomiuri.co.jp/

## 기능

### 기본 기능
[ ] **통합 검색 기능**
  - 사용자가 키워드 입력 시 모든 뉴스 사이트에서 병렬 검색
  - 검색 결과를 통합하여 하나의 리스트로 표시
  - 각 뉴스의 출처, 제목, 요약, 발행일, URL 정보 제공

[ ] **검색 결과 정렬 기능**
  - 날짜순 정렬 (최신순/과거순)
  - 관련도순 정렬
  - 출처별 그룹핑
  - 필터링 (특정 사이트만 보기, 날짜 범위 설정)

[ ] **인기 뉴스 대시보드**
  - 각 사이트별 인기/트렌딩 뉴스 목록
  - 실시간 업데이트 (30분 간격)
  - 카테고리별 분류 (정치, 경제, 스포츠, 엔터테인먼트 등)

### 추가 기능
[ ] **검색 히스토리**
  - 최근 검색어 저장 (로컬 스토리지)
  - 자주 검색하는 키워드 추천

[ ] **뉴스 요약 기능**
  - AI를 활용한 자동 뉴스 요약
  - 여러 사이트의 같은 주제 뉴스 통합 요약

## 기술적 구현 요구사항

### 웹 스크래핑
- 각 뉴스 사이트별 스크래핑 모듈 개발
- robots.txt 준수 및 rate limiting
- 동적 콘텐츠 처리 (JavaScript 렌더링)
- 오류 처리 및 fallback 메커니즘

### 데이터 처리
- 뉴스 데이터 정규화 (제목, 내용, 날짜, URL 등)
- 중복 뉴스 제거 로직
- 텍스트 인코딩 처리 (다국어 지원)

### 성능 최적화
- 비동기 병렬 스크래핑
- 메모리 캐싱 (간단한 in-memory cache)
- 검색 결과 페이지네이션

## 아키텍처 옵션 분석

### Option 1: 풀스택 (현재 계획) 
**구조**: Next.js Frontend + FastAPI Backend
- ✅ 완전한 제어권
- ✅ 복잡한 스크래핑 로직 구현 가능
- ❌ 배포 복잡성 증가
- ❌ 서버 비용 발생 가능

### Option 2: Next.js만 사용 (추천)
**구조**: Next.js + API Routes
- ✅ 단일 배포, Vercel 무료 사용
- ✅ 서버사이드 스크래핑 가능
- ❌ Serverless 함수 제한 (10초 타임아웃)
- ❌ 복잡한 스크래핑에는 제한적

### Option 3: RSS 기반 (가장 간단)
**구조**: Next.js + RSS 피드만 활용
- ✅ 매우 간단하고 안정적
- ✅ 빠른 개발
- ❌ 검색 기능 제한적
- ❌ 모든 사이트 지원 어려움

## 추천: Option 2 (Next.js API Routes)

개인 용도라면 **Next.js API Routes**만으로도 충분할 것 같습니다!

### 장점
- Vercel에서 무료 배포
- 백엔드 서버 관리 불필요  
- 서버사이드에서 CORS 문제 해결
- 간단한 스크래핑은 충분히 가능

### 구현 방식
```javascript
// app/api/search/route.js
import { scrapeNews } from '@/lib/scrapers';

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get('q');
  
  const results = await Promise.all([
    scrapeBBC(query),
    scrapeNYPost(query),
    // 각 사이트별 스크래핑
  ]);
  
  return Response.json(results.flat());
}
```

### 수정된 기술 스택

## 💻 처리 위치 및 성능 분석

### Option 1: 풀스택 (FastAPI Backend)
**로컬 개발**: 개발자 컴퓨터에서 백엔드 실행
**배포 후**: Railway/Render 서버에서 실행
**클라이언트 부담**: 없음 (서버에서 모든 처리)

### Option 2: Next.js API Routes  
**로컬 개발**: 개발자 컴퓨터에서 API Routes 실행 ⚠️
**배포 후**: Vercel 서버에서 실행 
**클라이언트 부담**: 없음 (서버에서 모든 처리)

### Option 3: 클라이언트 전용 스크래핑
**처리 위치**: 사용자 브라우저에서 직접 실행
**클라이언트 부담**: 높음 ❌ (노트북이 느려질 수 있음)

## 🎯 노트북 성능 고려한 최종 추천

개인적으로는 **Option 1 (FastAPI Backend)**을 추천합니다!

### 이유:
1. **로컬 개발도 편함**: 백엔드를 별도 터미널에서 실행
2. **개발 시 부담 분산**: 프론트엔드와 백엔드 분리 실행
3. **확장성**: 나중에 복잡한 기능 추가하기 쉬움
4. **디버깅**: 스크래핑 로그를 백엔드에서 쉽게 확인

### 대안: Docker로 개발 부담 줄이기
```yaml
# docker-compose.yml
version: '3.8'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    # 리소스 제한으로 노트북 보호
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
```

## 🚀 결론 및 수정된 추천

**노트북 성능 고려 시**: **Option 1 (FastAPI Backend)** 추천!

### 개발 방식:
1. **백엔드**: Docker로 리소스 제한하여 실행
2. **프론트엔드**: 별도 터미널에서 실행
3. **스크래핑**: 백엔드에서만 처리 (프론트엔드 부담 없음)

### 배포:
- **백엔드**: Railway 무료 플랜
- **프론트엔드**: Vercel 무료 플랜
- **총 비용**: 0원

## 기술 스택 (최종)

### Frontend
- **프레임워크**: Next.js 14 (App Router)
- **스타일링**: Tailwind CSS + shadcn/ui
- **상태관리**: React useState/useContext
- **HTTP 클라이언트**: fetch API
- **로컬 저장소**: localStorage (검색 히스토리)

### Backend (경량화)
- **프레임워크**: FastAPI (Python)
- **웹 스크래핑**: BeautifulSoup4 + requests
- **동적 콘텐츠**: Playwright (필요시에만)
- **캐싱**: 간단한 메모리 캐시
- **리소스 제한**: Docker로 CPU/메모리 제한

### 개발 환경
- **로컬 실행**: Docker Compose
- **리소스 제한**: 백엔드 0.5 CPU, 512MB 메모리
- **패키지 관리**: npm + pip
- **배포**: Vercel (Frontend) + Railway (Backend)

## 개발 우선순위

### Phase 1: 기본 MVP (최소 기능)
1. **Docker 개발 환경 설정** (리소스 제한 포함)
2. **FastAPI 백엔드**: 1-2개 사이트 스크래핑 (BBC만 우선)
3. **Next.js 프론트엔드**: 검색 UI + 결과 표시
4. **API 연동**: 기본 검색 기능

### Phase 2: 기능 확장  
1. 나머지 뉴스 사이트 추가 (점진적으로)
2. 정렬/필터링 기능
3. 검색 히스토리 (localStorage)
4. 로딩 상태 개선

### Phase 3: 고급 기능 (선택적)
1. 인기 뉴스 대시보드
2. AI 뉴스 요약 (OpenAI API)
3. 모바일 반응형 개선

## 폴더 구조 (최종)
```
news-search/
├── frontend/              # Next.js 앱
│   ├── app/
│   ├── components/
│   └── lib/
├── backend/               # FastAPI 앱 (경량화)
│   ├── app/
│   │   ├── scrapers/     # 각 사이트별 스크래퍼
│   │   ├── api/          # API 엔드포인트
│   │   └── main.py       # FastAPI 앱
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml     # 리소스 제한 포함
└── README.md
```
