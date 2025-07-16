# Railway 배포 가이드 🚂

## 📋 Railway 배포 단계

### 1️⃣ **Railway 프로젝트 생성**
```bash
# Railway CLI 설치 (선택사항)
npm install -g @railway/cli

# 또는 웹에서 railway.app 접속
```

### 2️⃣ **GitHub 연결**
1. Railway 웹사이트에서 "Deploy from GitHub" 선택
2. 이 레포지토리 선택
3. 백엔드 배포 설정

### 3️⃣ **환경 변수 설정**
Railway 대시보드에서 다음 환경 변수 설정:

```
MAX_WORKERS=2                    # 무료 플랜 최적화
PYTHONPATH=/app                  # Python 경로 설정
ALLOWED_ORIGINS=https://your-frontend-domain.com,http://localhost:3006
```

### 4️⃣ **배포 설정**
- **Root Directory**: `backend/` (중요!)
- **Build Command**: 자동 감지 (Dockerfile 사용)
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## ⚙️ **Railway 무료 플랜 최적화 설정**

### 🔧 **성능 최적화**
- **워커 수**: 2개 (메모리 절약)
- **메모리**: 512MB 제한
- **CPU**: 0.5 vCPU
- **네트워크**: 제한적 동시 연결

### 🐌 **느린 사이트 대응**
무료 플랜에서는 다음 사이트들이 특히 느릴 수 있습니다:
- Bangkok Post (5.22초)
- Daily Mail (3.69초)
- NY Post (2.15초)

### 💡 **성능 개선 팁**
1. **사이트 선택적 활용**: 빠른 사이트 위주로 사용
2. **검색어 최적화**: 구체적인 키워드 사용
3. **페이지 수 제한**: per_site_limit 줄이기

## 🌐 **CORS 설정**

프론트엔드 배포 후 `ALLOWED_ORIGINS` 환경 변수에 도메인 추가:
```
ALLOWED_ORIGINS=https://your-frontend.vercel.app,https://your-frontend.netlify.app
```

## 📊 **예상 성능**

Railway 무료 플랜에서의 예상 응답 시간:
- **빠른 검색**: 3-5초 (빠른 사이트만)
- **전체 검색**: 8-12초 (모든 사이트)
- **첫 요청**: 15-20초 (콜드 스타트)

## ⚠️ **주의사항**

1. **콜드 스타트**: 첫 요청은 느림 (15-20초)
2. **메모리 제한**: 512MB 초과시 재시작
3. **타임아웃**: 긴 요청은 실패 가능
4. **동시 사용자**: 제한적 (1-2명)

## 🔄 **자동 배포 설정**

이미 `railway.toml` 설정 완료:
- GitHub push 시 자동 배포
- 헬스체크 자동 설정
- 재시작 정책 설정

## 🚀 **배포 명령어**

```bash
# Railway CLI 사용시
railway login
railway link
railway up

# 또는 웹에서 Deploy 버튼 클릭
```

## 📈 **성능 모니터링**

Railway 대시보드에서 확인 가능:
- 메모리 사용량
- CPU 사용량
- 응답 시간
- 에러 로그

---

**💰 Railway 무료 플랜으로도 충분히 사용 가능합니다!** 