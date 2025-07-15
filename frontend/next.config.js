/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    appDir: true,
  },
  images: {
    unoptimized: true, // 개발 단계에서 모든 이미지 도메인 허용
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*', // 백엔드로 프록시
      },
    ]
  },
}

module.exports = nextConfig 