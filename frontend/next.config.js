/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true, // 개발 단계에서 모든 이미지 도메인 허용
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**", // 모든 HTTPS 도메인 허용
      },
      {
        protocol: "http",
        hostname: "**", // 모든 HTTP 도메인 허용 (개발용)
      },
    ],
    domains: [
      "ichef.bbci.co.uk",
      "bbc.co.uk",
      "bbcimg.co.uk",
      "cdn.cnn.com",
      "i.dailymail.co.uk",
      "static.independent.co.uk",
      "www.thethaiger.com",
      "cdn.bangkokpost.com",
      "static.bangkokpost.com",
      "vietnamnet.vn",
      "i1-vnexpress.vnecdn.net",
      "vcdn-english.vnecdn.net",
      "vcdn1-thethao.vnecdn.net",
      "img.scmp.com",
      "cdn.i-scmp.com",
      "nypost.com",
      "thesun.co.uk",
      "www.asahicom.jp",
      "www.yomiuri.co.jp",
      "d2x7ubddzu7b7n.cloudfront.net",
    ],
  },
  // 프로덕션에서는 환경변수를 통해 API 연결 (프록시 제거)
};

module.exports = nextConfig;
