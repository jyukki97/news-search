'use client'

import { useState, useEffect } from 'react'
import SearchBar from '@/components/SearchBar'
import NewsCard from '@/components/NewsCard'
import { searchNews, getTrendingNews, NewsArticle, SearchResponse, TrendingResponse } from '@/lib/api'

export default function Home() {
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null)
  const [trendingNews, setTrendingNews] = useState<TrendingResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [trendingLoading, setTrendingLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [groupBySource, setGroupBySource] = useState(false)
  const [showDateFilter, setShowDateFilter] = useState(false)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [showTrending, setShowTrending] = useState(true)
  const [showSiteFilter, setShowSiteFilter] = useState(false)

  // 뉴스 사이트 목록 및 체크박스 상태
  const newsSites = [
    { id: 'bbc', name: 'BBC News', icon: '🇬🇧' },
    { id: 'thesun', name: 'The Sun', icon: '☀️' },
    { id: 'nypost', name: 'NY Post', icon: '🗞️' },
    { id: 'dailymail', name: 'Daily Mail', icon: '📧' },
    { id: 'scmp', name: 'SCMP', icon: '🇭🇰' },
    { id: 'vnexpress', name: 'VN Express', icon: '🇻🇳' },
    { id: 'bangkokpost', name: 'Bangkok Post', icon: '🇹🇭' },
    { id: 'asahi', name: 'Asahi Shimbun', icon: '🇯🇵' },
    { id: 'yomiuri', name: 'Yomiuri Shimbun', icon: '📰' }
  ]

  const [selectedSites, setSelectedSites] = useState<{[key: string]: boolean}>(() => {
    const initial: {[key: string]: boolean} = {}
    newsSites.forEach(site => {
      initial[site.id] = true // 기본적으로 모든 사이트 선택
    })
    return initial
  })

  const categories = [
    { id: 'all', name: '전체', icon: '📰' },
    { id: 'news', name: '일반뉴스', icon: '📰' },
    { id: 'business', name: '비즈니스', icon: '💼' },
    { id: 'technology', name: '기술', icon: '💻' },
    { id: 'sports', name: '스포츠', icon: '⚽' },
    { id: 'entertainment', name: '엔터', icon: '🎬' },
    { id: 'health', name: '건강', icon: '🏥' },
    { id: 'world', name: '국제', icon: '🌍' }
  ]

  // 컴포넌트 마운트 시 트렌딩 뉴스 로드
  useEffect(() => {
    loadTrendingNews('all')
    
    // 30분(1800초)마다 자동 업데이트
    const autoRefreshInterval = setInterval(() => {
      if (showTrending) {
        loadTrendingNews(selectedCategory)
        console.log('트렌딩 뉴스 자동 업데이트')
      }
    }, 30 * 60 * 1000) // 30분 = 30 * 60 * 1000 밀리초
    
    // 컴포넌트 언마운트 시 타이머 정리
    return () => {
      clearInterval(autoRefreshInterval)
    }
  }, [showTrending, selectedCategory])

  // 수동 새로고침 함수
  const refreshTrendingNews = () => {
    loadTrendingNews(selectedCategory)
  }

  const loadTrendingNews = async (category: string) => {
    setTrendingLoading(true)
    try {
      const result = await getTrendingNews(category, 3, 'all') // 사이트당 3개씩
      setTrendingNews(result)
      setSelectedCategory(category)
    } catch (error) {
      console.error('트렌딩 뉴스 로드 실패:', error)
    } finally {
      setTrendingLoading(false)
    }
  }

  // 선택된 사이트들을 API 파라미터 형식으로 변환
  const getSelectedSourcesString = () => {
    const selected = Object.entries(selectedSites)
      .filter(([_, isSelected]) => isSelected)
      .map(([siteId, _]) => siteId)
    
    return selected.length === newsSites.length ? 'all' : selected.join(',')
  }

  // 선택된 사이트 개수
  const selectedSitesCount = Object.values(selectedSites).filter(Boolean).length

  // 전체 선택/해제
  const toggleAllSites = () => {
    const allSelected = selectedSitesCount === newsSites.length
    const newSelection: {[key: string]: boolean} = {}
    
    newsSites.forEach(site => {
      newSelection[site.id] = !allSelected
    })
    
    setSelectedSites(newSelection)
  }

  // 개별 사이트 토글
  const toggleSite = (siteId: string) => {
    setSelectedSites(prev => ({
      ...prev,
      [siteId]: !prev[siteId]
    }))
  }

  const handleSearch = async (searchQuery: string, page: number = 1) => {
    setLoading(true)
    if (page === 1) {
      setQuery(searchQuery)
      setCurrentPage(1)
    }
    
    try {
      const sourcesParam = getSelectedSourcesString()
      const result = await searchNews(
        searchQuery, 
        page, 
        3, // 각 사이트에서 3개씩
        sourcesParam, // 선택된 사이트들만
        'date_desc', // sort
        dateFrom || undefined,
        dateTo || undefined
      )
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

  const resetDateFilter = () => {
    setDateFrom('')
    setDateTo('')
    if (query) {
      handleSearch(query, 1) // 날짜 필터 초기화 후 재검색
    }
  }

  // 출처별로 기사 그룹핑
  const groupArticlesBySource = (articles: NewsArticle[]) => {
    const grouped: { [key: string]: NewsArticle[] } = {}
    articles.forEach(article => {
      const source = article.source
      if (!grouped[source]) {
        grouped[source] = []
      }
      grouped[source].push(article)
    })
    return grouped
  }

  return (
    <div className="space-y-8">
      {/* 검색 섹션 */}
      <div className="text-center">
        <h2 className="text-3xl font-bold text-gray-900 mb-4">
          글로벌 뉴스 검색
        </h2>
        <p className="text-gray-600 mb-6">
          9개 글로벌 뉴스 사이트에서 실시간으로 뉴스를 검색하세요
        </p>
        
        {/* 검색창과 사이트 필터 */}
        <div className="flex flex-col lg:flex-row items-start lg:items-center gap-6 max-w-6xl mx-auto">
          {/* 사이트 필터 */}
          <div className="w-full lg:w-80 flex-shrink-0">
            <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-semibold text-gray-800 text-sm">뉴스 사이트 선택</h4>
                <button
                  onClick={() => setShowSiteFilter(!showSiteFilter)}
                  className="lg:hidden text-xs text-blue-600 hover:text-blue-800"
                >
                  {showSiteFilter ? '숨기기' : '표시'}
                </button>
              </div>
              
              <div className={`space-y-2 ${showSiteFilter || 'hidden'} lg:block`}>
                {/* 전체 선택/해제 버튼 */}
                <div className="flex items-center justify-between pb-2 border-b border-gray-300">
                  <button
                    onClick={toggleAllSites}
                    className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                  >
                    {selectedSitesCount === newsSites.length ? '전체 해제' : '전체 선택'}
                  </button>
                  <span className="text-xs text-gray-500">
                    {selectedSitesCount}/{newsSites.length}개 선택
                  </span>
                </div>
                
                {/* 사이트별 체크박스 */}
                <div className="grid grid-cols-1 gap-1 max-h-60 overflow-y-auto">
                  {newsSites.map((site) => (
                    <label
                      key={site.id}
                      className="flex items-center space-x-2 p-2 hover:bg-gray-100 rounded cursor-pointer transition-colors"
                    >
                      <input
                        type="checkbox"
                        checked={selectedSites[site.id] || false}
                        onChange={() => toggleSite(site.id)}
                        className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus:ring-2"
                      />
                      <span className="text-sm text-gray-700 flex items-center">
                        <span className="mr-1">{site.icon}</span>
                        {site.name}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          </div>
          
          {/* 검색창 */}
          <div className="flex-1 w-full">
            <SearchBar onSearch={(query) => handleSearch(query)} loading={loading} />
            
            {/* 선택된 사이트 요약 */}
            <div className="mt-2 text-sm text-gray-600 text-center">
              {selectedSitesCount > 0 ? (
                selectedSitesCount === newsSites.length ? (
                  <span>📰 모든 사이트에서 검색</span>
                ) : (
                  <span>📰 {selectedSitesCount}개 사이트에서 검색</span>
                )
              ) : (
                <span className="text-red-500">⚠️ 검색할 사이트를 선택해주세요</span>
              )}
            </div>
          </div>
        </div>
        
        {/* 날짜 필터 토글 및 입력 */}
        <div className="mt-4 space-y-3">
          <button
            onClick={() => setShowDateFilter(!showDateFilter)}
            className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
          >
            📅 날짜 범위 필터 {showDateFilter ? '숨기기' : '표시'}
          </button>
          
          {showDateFilter && (
            <div className="flex flex-col sm:flex-row items-center justify-center space-y-2 sm:space-y-0 sm:space-x-4 p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center space-x-2">
                <label htmlFor="date-from" className="text-sm font-medium text-gray-700">
                  시작:
                </label>
                <input
                  id="date-from"
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="px-3 py-1 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              <div className="flex items-center space-x-2">
                <label htmlFor="date-to" className="text-sm font-medium text-gray-700">
                  종료:
                </label>
                <input
                  id="date-to"
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="px-3 py-1 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              <div className="flex space-x-2">
                <button
                  onClick={() => query && handleSearch(query, 1)}
                  className="px-3 py-1 bg-blue-500 text-white rounded-md text-sm hover:bg-blue-600 transition-colors"
                >
                  적용
                </button>
                <button
                  onClick={resetDateFilter}
                  className="px-3 py-1 bg-gray-500 text-white rounded-md text-sm hover:bg-gray-600 transition-colors"
                >
                  초기화
                </button>
              </div>
            </div>
          )}
          
          {/* 활성 필터 표시 */}
          {(dateFrom || dateTo) && (
            <div className="text-sm text-blue-600">
              📅 날짜 필터 활성: 
              {dateFrom && ` ${dateFrom}부터`}
              {dateTo && ` ${dateTo}까지`}
              <button
                onClick={resetDateFilter}
                className="ml-2 text-red-500 hover:text-red-700"
              >
                ✕
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 트렌딩 뉴스 대시보드 */}
      {!query && showTrending && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-2xl font-bold text-gray-900">🔥 트렌딩 뉴스</h3>
            <div className="flex items-center space-x-3">
              <button
                onClick={refreshTrendingNews}
                disabled={trendingLoading}
                className="px-3 py-1 bg-green-500 text-white rounded-lg text-sm hover:bg-green-600 transition-colors disabled:opacity-50"
              >
                🔄 새로고침
              </button>
              <button
                onClick={() => setShowTrending(false)}
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                숨기기
              </button>
            </div>
          </div>

          {/* 카테고리 선택 */}
          <div className="flex flex-wrap gap-2 justify-center">
            {categories.map((category) => (
              <button
                key={category.id}
                onClick={() => loadTrendingNews(category.id)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  selectedCategory === category.id
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {category.icon} {category.name}
              </button>
            ))}
          </div>

          {/* 트렌딩 뉴스 내용 */}
          {trendingLoading ? (
            <div className="text-center py-8">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <p className="mt-2 text-gray-600">트렌딩 뉴스 로딩 중...</p>
            </div>
          ) : trendingNews && trendingNews.total_articles > 0 ? (
            <div className="space-y-8">
              {Object.entries(trendingNews.trending_by_source).map(([source, articles]) => (
                <div key={source} className="space-y-4">
                  {/* 출처 헤더 */}
                  <div className="border-b border-gray-200 pb-2">
                    <h4 className="text-lg font-semibold text-gray-800 flex items-center">
                      📰 {source}
                      <span className="ml-2 px-2 py-1 bg-orange-100 text-orange-700 text-xs rounded-full">
                        {articles.length}개
                      </span>
                    </h4>
                  </div>
                  
                  {/* 출처별 기사 그리드 */}
                  <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                    {articles.map((article: NewsArticle, index: number) => (
                      <NewsCard key={`${source}-trending-${index}`} article={article} />
                    ))}
                  </div>
                </div>
              ))}
              
              {/* 업데이트 시간 */}
              <div className="text-center text-xs text-gray-500 space-y-1">
                <div>
                  마지막 업데이트: {new Date(trendingNews.last_updated).toLocaleString()}
                </div>
                <div className="flex items-center justify-center space-x-2">
                  <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
                  <span>30분마다 자동 업데이트</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              트렌딩 뉴스를 불러올 수 없습니다.
            </div>
          )}
        </div>
      )}

      {/* 검색 결과 숨김/표시 버튼 */}
      {!query && !showTrending && (
        <div className="text-center">
          <button
            onClick={() => setShowTrending(true)}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
          >
            🔥 트렌딩 뉴스 보기
          </button>
        </div>
      )}

      {/* 로딩 상태 */}
      {loading && (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="mt-2 text-gray-600">검색 중...</p>
        </div>
      )}

      {/* 검색 결과 */}
      {searchResult && !loading && (
        <div className="space-y-6">
          {searchResult.total_articles > 0 ? (
            <div className="space-y-6">
              {/* 검색 결과 헤더 */}
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-4 sm:space-y-0">
                <div className="text-sm text-gray-600">
                  <strong>총 {searchResult.total_articles}개</strong> 기사를 찾았습니다.
                  <br />
                  <span className="text-xs text-gray-500">
                    활성 사이트: {searchResult.active_sources.join(', ')}
                  </span>
                </div>
                
                {/* 페이지네이션 및 그룹핑 토글 */}
                <div className="flex items-center space-x-4">
                  {/* 그룹핑 토글 */}
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => setGroupBySource(!groupBySource)}
                      className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                        groupBySource
                          ? 'bg-blue-500 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      📑 출처별 그룹핑
                    </button>
                  </div>

                  {/* 페이지네이션 */}
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={handlePrevPage}
                      disabled={currentPage <= 1}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        currentPage <= 1
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

              {/* 기사 표시 */}
              {groupBySource ? (
                // 출처별 그룹핑 표시
                <div className="space-y-8">
                  {Object.entries(groupArticlesBySource(searchResult.articles)).map(([source, articles]) => (
                    <div key={source} className="space-y-4">
                      {/* 출처 헤더 */}
                      <div className="border-b border-gray-200 pb-2">
                        <h3 className="text-lg font-semibold text-gray-800 flex items-center">
                          📰 {source}
                          <span className="ml-2 px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full">
                            {articles.length}개
                          </span>
                        </h3>
                      </div>
                      
                      {/* 출처별 기사 그리드 */}
                      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                        {articles.map((article: NewsArticle, index: number) => (
                          <NewsCard key={`${source}-${currentPage}-${index}`} article={article} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                // 기본 그리드 표시
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                  {searchResult.articles.map((article: NewsArticle, index: number) => (
                    <NewsCard key={`${currentPage}-${index}`} article={article} />
                  ))}
                </div>
              )}

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
              {selectedSitesCount === 0 ? (
                <div>
                  <p>검색할 사이트를 선택해주세요.</p>
                  <button
                    onClick={() => setShowSiteFilter(true)}
                    className="mt-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
                  >
                    사이트 선택하기
                  </button>
                </div>
              ) : (
                '검색 결과가 없습니다. 다른 키워드로 시도해보세요.'
              )}
            </div>
          )}
        </div>
      )}

      {/* 초기 안내 */}
      {!query && !showTrending && (
        <div className="text-center py-12">
          <div className="text-gray-400 text-lg">
            위의 검색창에 키워드를 입력해보세요
          </div>
          <div className="mt-4 text-sm text-gray-500">
            예: climate change, technology, business
          </div>
          <div className="mt-6 text-xs text-gray-400">
            💡 선택된 뉴스 사이트에서 페이지별로 3개씩 기사를 가져옵니다
          </div>
        </div>
      )}
    </div>
  )
} 