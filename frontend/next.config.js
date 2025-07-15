/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    appDir: true,
  },
  images: {
    domains: [
      'ichef.bbci.co.uk',
      'c.files.bbci.co.uk',
      'www.bbc.com',
      'bbc.com',
      'nypost.com',
      'wp.com',
      'i0.wp.com',
      'i1.wp.com',
      'i2.wp.com',
      'thesun.co.uk',
      'www.thesun.co.uk',
      'dailymail.co.uk',
      'www.dailymail.co.uk',
      'i.dailymail.co.uk',
      'scmp.com',
      'www.scmp.com',
      'cdn.i-scmp.com'
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