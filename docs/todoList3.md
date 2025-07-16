https://apigw.scmp.com/content-delivery/v2?extensions=%7B%22persistedQuery%22%3A%7B%22sha256Hash%22%3A%2205a3902acc7f34a4abcf1db1cb2b124fcc285f1e725554db4b2ce5959e5c8782%22%2C%22version%22%3A1%7D%7D&operationName=searchResultPanelQuery&variables=%7B%22articleTypeIds%22%3A%5B%5D%2C%22contentTypes%22%3A%5B%22ARTICLE%22%2C%22VIDEO%22%2C%22GALLERY%22%5D%2C%22first%22%3A10%2C%22paywallTypeIds%22%3A%5B%5D%2C%22query%22%3A%22sports%22%2C%22sectionIds%22%3A%5B%5D%7D

:authority
apigw.scmp.com
:method
GET
:path
/content-delivery/v2?extensions=%7B%22persistedQuery%22%3A%7B%22sha256Hash%22%3A%2205a3902acc7f34a4abcf1db1cb2b124fcc285f1e725554db4b2ce5959e5c8782%22%2C%22version%22%3A1%7D%7D&operationName=searchResultPanelQuery&variables=%7B%22articleTypeIds%22%3A%5B%5D%2C%22contentTypes%22%3A%5B%22ARTICLE%22%2C%22VIDEO%22%2C%22GALLERY%22%5D%2C%22first%22%3A10%2C%22paywallTypeIds%22%3A%5B%5D%2C%22query%22%3A%22sports%22%2C%22sectionIds%22%3A%5B%5D%7D
:scheme
https
accept
*/*
accept-encoding
gzip, deflate, br, zstd
accept-language
ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7
apikey
MyYvyg8M9RTaevVlcIRhN5yRIqqVssNY
content-type
application/json
if-none-match
W/"cdd7-DiC1PbIcNu0Mk0otZB97zGqNKks"
origin
https://www.scmp.com
priority
u=1, i
referer
https://www.scmp.com/
sec-ch-ua
"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"
sec-ch-ua-mobile
?0
sec-ch-ua-platform
"macOS"
sec-fetch-dest
empty
sec-fetch-mode
cors
sec-fetch-site
same-site
user-agent
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36



[x] scmp 검색이 안되고있음. 메인 페이지 기사들 가져오는 듯. ✅ **완료**: GraphQL API 구현으로 실제 검색 작동
[x] 날짜 필터, 출처별 그룹핑 2개 ✅ **완료**: 백엔드 API + 프론트엔드 UI 모두 구현 

## 구현 완료 사항

### SCMP GraphQL API 검색 수정
- ✅ 실제 SCMP GraphQL API 사용하도록 hybrid_scmp_scraper.py 수정
- ✅ todoList3.md의 API 정보 활용하여 정확한 검색 구현
- ✅ GraphQL 응답 파싱 로직 최적화
- ✅ 검색 결과 정상 작동 확인

### 백엔드 API 개선
- ✅ news_router.py에 `group_by_source` 파라미터 추가
- ✅ 출처별 그룹핑 기능 완전 구현
- ✅ 날짜 필터링 기능 이미 존재하던 것 확인 및 활용
- ✅ API 응답 구조 개선 (articles_by_source 필드 추가)

### 프론트엔드 UI 완성
- ✅ api.ts에 groupBySource 파라미터 추가
- ✅ 날짜 필터 UI 이미 완벽하게 구현되어 있었음
- ✅ 출처별 그룹핑 토글 버튼 백엔드 API 연동
- ✅ 그룹핑 옵션 변경시 자동 재검색 기능

### 테스트 및 확인
- ✅ SCMP "sports" 검색으로 실제 스포츠 기사 검색 확인
- ✅ 출처별 그룹핑 정상 작동 확인
- ✅ 날짜 필터와 그룹핑 동시 사용 테스트 완료
- ✅ 프론트엔드 UI (http://localhost:3006) 정상 작동 확인

### 커밋 완료
- ✅ 모든 변경사항 git 커밋 완료
- ✅ 의미있는 커밋 메시지로 변경 내역 기록 