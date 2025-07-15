'use client'

import { useState } from 'react'
import SearchBar from '@/components/SearchBar'
import NewsCard from '@/components/NewsCard'
import { searchNews, NewsArticle, SearchResponse } from '@/lib/api'

export default function Home() {
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [currentPage, setCurrentPage] = useState(1)

  const handleSearch = async (searchQuery: string, page: number = 1) => {
    setLoading(true)
    if (page === 1) {
      setQuery(searchQuery)
      setCurrentPage(1)
    }
    
    try {
      const result = await searchNews(searchQuery, page, 3) // 각 사이트에서 3개씩
      setSearchResult(result)
      setCurrentPage(page)
    } catch (error) {
      console.error('검색 실패:', error)
      setSearchResult(null)
    } finally {
      setLoading(false)
    }
  }

  const handleNextPage = () => {
    if (query && searchResult?.has_next_page) {
      handleSearch(query, currentPage + 1)
    }
  }

  const handlePrevPage = () => {
    if (query && currentPage > 1) {
      handleSearch(query, currentPage - 1)
    }
  }

  return (
    <div className="space-y-8">
      {/* 검색 섹션 */}
      <div className="text-center">
        <h2 className="text-3xl font-bold text-gray-900 mb-4">
          글로벌 뉴스 검색
        </h2>
        <p className="text-gray-600 mb-6">
          9개 주요 뉴스 사이트에서 각각 3개씩 최신 기사를 가져옵니다
        </p>
        
        <SearchBar onSearch={handleSearch} loading={loading} />
        
        {/* 지원 사이트 안내 */}
        <div className="mt-4 text-sm text-gray-500">
          🌍 <strong>지원 사이트:</strong> BBC News, The Sun, NY Post, Daily Mail, SCMP, VN Express, Bangkok Post, Asahi Shimbun, Yomiuri Shimbun
        </div>
      </div>

      {/* 검색 결과 */}
      {query && (
        <div>
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
            </div>
          ) : searchResult ? (
            <div>
              {/* 검색 결과 헤더 */}
              <div className="mb-8">
                <h3 className="text-2xl font-bold text-gray-900 mb-2">
                  &ldquo;{query}&rdquo; 검색 결과
                </h3>
                <div className="flex items-center justify-between">
                  <div className="text-gray-600">
                    페이지 {currentPage} • 총 {searchResult.total_articles}개 기사 • {searchResult.active_sources.length}개 사이트
                  </div>
                  
                  {/* 페이지네이션 버튼 */}
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={handlePrevPage}
                      disabled={currentPage === 1}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        currentPage === 1
                          ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                          : 'bg-blue-500 text-white hover:bg-blue-600'
                      }`}
                    >
                      ← 이전
                    </button>
                    <span className="px-3 py-2 bg-gray-100 rounded-lg text-sm font-medium">
                      {currentPage}
                    </span>
                    <button
                      onClick={handleNextPage}
                      disabled={!searchResult.has_next_page}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        !searchResult.has_next_page
                          ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                          : 'bg-blue-500 text-white hover:bg-blue-600'
                      }`}
                    >
                      다음 →
                    </button>
                  </div>
                </div>
              </div>

              {/* 기사 그리드 */}
              <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                {searchResult.articles.map((article: NewsArticle, index: number) => (
                  <NewsCard key={`${currentPage}-${index}`} article={article} />
                ))}
              </div>

              {/* 활성 사이트 정보 */}
              <div className="mt-8 p-4 bg-blue-50 rounded-lg border border-blue-200">
                <div className="text-center text-sm text-blue-700">
                  📰 <strong>이번 페이지 활성 사이트:</strong> {searchResult.active_sources.join(', ')}
                  <br />
                  각 사이트에서 최대 {searchResult.per_site_limit}개씩 가져왔습니다.
                </div>
              </div>
            </div>
          ) : (
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
          <div className="mt-6 text-xs text-gray-400">
            💡 각 뉴스 사이트에서 페이지별로 3개씩 기사를 가져와서 총 최대 27개까지 표시됩니다
          </div>
        </div>
      )}
    </div>
  )
} 