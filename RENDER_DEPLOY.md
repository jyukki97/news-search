# 🚀 Render 배포 가이드

이 프로젝트를 Render에 배포하는 방법을 설명합니다.

## 📋 배포 개요

- **백엔드**: FastAPI (Python) - Web Service
- **프론트엔드**: Next.js (Node.js) - Web Service  
- **배포 방식**: 별도 서비스로 분리 배포
- **요금**: 무료 플랜 사용 가능

## 🏗️ 1단계: 백엔드 배포

### 1.1 Render Dashboard에서 새 Web Service 생성
1. [Render Dashboard](https://dashboard.render.com) 접속
2. "New" → "Web Service" 선택
3. GitHub 저장소 연결

### 1.2 백엔드 서비스 설정
```yaml
Name: news-search-backend
Environment: Docker
Region: Singapore (또는 원하는 지역)
Branch: main
Root Directory: backend
Dockerfile Path: ./Dockerfile
```

**참고**: 백엔드는 기존 Dockerfile을 사용하여 Docker 방식으로 배포됩니다. 별도 빌드 명령어 설정이 불필요합니다.

### 1.3 환경변수 설정
```bash
PYTHONPATH=/app
MAX_WORKERS=1
CORS_ORIGINS=https://news-search-frontend.onrender.com,http://localhost:3000
```

### 1.4 고급 설정
```yaml
Health Check Path: /api/news/categories
Auto-Deploy: Yes
Plan: Free
```

## 🎨 2단계: 프론트엔드 배포

### 2.1 Render Dashboard에서 새 Web Service 생성
1. "New" → "Web Service" 선택  
2. 같은 GitHub 저장소 선택

### 2.2 프론트엔드 서비스 설정
```yaml
Name: news-search-frontend
Environment: Node
Region: Singapore (백엔드와 동일 지역 권장)
Branch: main
Root Directory: frontend
Build Command: npm install && npm run build
Start Command: npm start
```

### 2.3 환경변수 설정
```bash
NEXT_PUBLIC_API_URL=https://news-search-backend.onrender.com
NODE_ENV=production
```

### 2.4 고급 설정
```yaml
Auto-Deploy: Yes
Plan: Free
```

## 🔧 3단계: 배포 후 설정

### 3.1 백엔드 URL 확인
배포 완료 후 백엔드 URL을 확인하고 프론트엔드 환경변수를 업데이트:

1. 백엔드 서비스 → Settings → Environment Variables
2. `CORS_ORIGINS`에 실제 프론트엔드 URL 추가

### 3.2 프론트엔드 API URL 업데이트
1. 프론트엔드 서비스 → Settings → Environment Variables  
2. `NEXT_PUBLIC_API_URL`을 실제 백엔드 URL로 업데이트

## 🧪 4단계: 배포 테스트

### 4.1 백엔드 테스트
```bash
# Health Check
curl https://news-search-backend.onrender.com/health

# 카테고리 API
curl https://news-search-backend.onrender.com/api/news/categories
```

### 4.2 프론트엔드 테스트
브라우저에서 프론트엔드 URL 접속하여 기능 테스트

## 🌍 5단계: 도메인 설정 (선택사항)

### 5.1 커스텀 도메인 연결
1. Render Dashboard → Service → Settings → Custom Domains
2. 원하는 도메인 추가
3. DNS 설정 업데이트

## 🔄 로컬 개발 환경 설정

### 환경변수 파일 생성
```bash
# frontend/.env.local 파일 생성
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 개발 서버 실행
```bash
# 백엔드
cd backend && uvicorn app.main:app --reload --port 8000

# 프론트엔드  
cd frontend && npm run dev
```

## 🚨 주의사항

### 무료 플랜 제한사항
- **Sleep Mode**: 15분 비활성화 시 슬립 모드 진입
- **대역폭**: 월 100GB 제한
- **빌드 시간**: 월 500분 제한

### 보안 설정
- CORS 설정을 적절히 제한 (`*` 사용 금지)
- 환경변수로 민감한 정보 관리
- HTTPS 사용 강제

## 🔧 트러블슈팅

### 일반적인 문제들

#### 1. CORS 오류
```bash
# 백엔드 환경변수 확인
CORS_ORIGINS=https://your-frontend.onrender.com
```

#### 2. API 연결 실패
```bash
# 프론트엔드 환경변수 확인  
NEXT_PUBLIC_API_URL=https://your-backend.onrender.com
```

#### 3. 빌드 실패
```bash
# 의존성 문제 - package.json/requirements.txt 확인
# Node/Python 버전 확인
```

#### 4. 슬립 모드
- 무료 플랜은 15분 후 슬립 모드 진입
- 첫 요청 시 30초 정도 소요될 수 있음

## 📈 모니터링

### 로그 확인
1. Render Dashboard → Service → Logs
2. 실시간 로그 모니터링 가능

### 메트릭 확인
1. Render Dashboard → Service → Metrics
2. CPU/메모리 사용량 확인

## 💰 비용 최적화

### 무료 플랜 활용
- 개인 프로젝트나 포트폴리오용으로 적합
- 슬립 모드 활용으로 비용 절약

### 유료 플랜 고려사항
- 24/7 가동 필요시 Starter 플랜($7/월) 고려
- 높은 트래픽 예상시 Pro 플랜 고려

## 🔗 참고 링크

- [Render 공식 문서](https://render.com/docs)
- [FastAPI 배포 가이드](https://fastapi.tiangolo.com/deployment/)
- [Next.js 배포 가이드](https://nextjs.org/docs/deployment) 