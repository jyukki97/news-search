import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'News Search',
  description: '여러 뉴스 사이트를 한번에 검색하는 서비스',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ko">
      <body className={inter.className}>
        <div className="min-h-screen bg-gray-50">
          <header className="bg-white shadow-sm border-b">
            <div className="max-w-6xl mx-auto px-4 py-4">
              <h1 className="text-2xl font-bold text-gray-900">
                📰 News Search
              </h1>
              <p className="text-sm text-gray-600 mt-1">
                여러 뉴스 사이트를 한번에 검색하세요
              </p>
            </div>
          </header>
          <main className="max-w-6xl mx-auto px-4 py-8">
            {children}
          </main>
        </div>
      </body>
    </html>
  )
} 