'use client'

import { useState } from 'react'
import SearchBar from '@/components/SearchBar'
import NewsCard from '@/components/NewsCard'
import { searchNews } from '@/lib/api'

export default function Home() {
  const [articles, setArticles] = useState([])
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')

  const handleSearch = async (searchQuery: string) => {
    setLoading(true)
    setQuery(searchQuery)
    
    try {
      const result = await searchNews(searchQuery)
      setArticles(result.articles || [])
    } catch (error) {
      console.error('검색 실패:', error)
      setArticles([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      {/* 검색 섹션 */}
      <div className="text-center">
        <h2 className="text-3xl font-bold text-gray-900 mb-4">
          뉴스를 검색해보세요
        </h2>
        <p className="text-gray-600 mb-8">
          BBC 뉴스에서 실시간으로 검색 결과를 가져옵니다
        </p>
        <SearchBar onSearch={handleSearch} loading={loading} />
      </div>

      {/* 검색 결과 */}
      {query && (
        <div>
          <h3 className="text-xl font-semibold text-gray-900 mb-4">
            &ldquo;{query}&rdquo; 검색 결과 ({articles.length}개)
          </h3>
          
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
            </div>
          ) : (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {articles.map((article: any, index: number) => (
                <NewsCard key={index} article={article} />
              ))}
            </div>
          )}
          
          {!loading && articles.length === 0 && query && (
            <div className="text-center py-12 text-gray-500">
              검색 결과가 없습니다. 다른 키워드로 시도해보세요.
            </div>
          )}
        </div>
      )}

      {/* 초기 안내 */}
      {!query && (
        <div className="text-center py-12">
          <div className="text-gray-400 text-lg">
            위의 검색창에 키워드를 입력해보세요
          </div>
          <div className="mt-4 text-sm text-gray-500">
            예: climate change, technology, business
          </div>
        </div>
      )}
    </div>
  )
} 