/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    appDir: true,
  },
  images: {
    domains: [
      // BBC News
      'ichef.bbci.co.uk',
      'c.files.bbci.co.uk',
      'static.files.bbci.co.uk',
      'www.bbc.com',
      'bbc.com',
      // NY Post
      'nypost.com',
      'wp.com',
      'i0.wp.com',
      'i1.wp.com',
      'i2.wp.com',
      // The Sun
      'thesun.co.uk',
      'www.thesun.co.uk',
      // Daily Mail
      'dailymail.co.uk',
      'www.dailymail.co.uk',
      'i.dailymail.co.uk',
      // SCMP
      'scmp.com',
      'www.scmp.com',
      'cdn.i-scmp.com',
      // VN Express
      'e.vnexpress.net',
      'vnexpress.net',
      'vcdn.vnecdn.net',
      'vcdn1-english.vnecdn.net',
      'vcdn2-english.vnecdn.net',
      'vcdn3-english.vnecdn.net',
      'i1-vnexpress.vnecdn.net',
      'i2-vnexpress.vnecdn.net',
      // Bangkok Post
      'www.bangkokpost.com',
      'bangkokpost.com',
      'static.bangkokpost.com',
      'bkkpostmedia.com',
      // Asahi Shimbun
      'p.potaufeu.asahi.com',
      'www.asahi.com',
      'asahi.com',
      'webronza.asahi.com',
      // Yomiuri Shimbun
      'www.yomiuri.co.jp',
      'yomiuri.co.jp',
      'www.yomiuri.com'
    ],
    unoptimized: false,
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