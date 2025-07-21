/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true, // 개발 단계에서 모든 이미지 도메인 허용
  },
  // 프로덕션에서는 환경변수를 통해 API 연결 (프록시 제거)
}

module.exports = nextConfig 