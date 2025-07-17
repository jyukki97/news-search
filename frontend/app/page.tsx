'use client'

import { useState, useEffect } from 'react'
import SearchBar from '@/components/SearchBar'
import NewsCard from '@/components/NewsCard'
import { searchNews, getTrendingNews, getTrendingNewsStream, searchNewsStream, NewsArticle, SearchResponse, TrendingResponse, StreamingMessage, SearchStreamingMessage } from '@/lib/api'

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
  const [sortOption, setSortOption] = useState('date_desc')
  
  // 뷰 모드 상태 추가 (트렌딩/검색 구별)
  const [viewMode, setViewMode] = useState<'trending' | 'search'>('trending')
  const [pendingSitesUpdate, setPendingSitesUpdate] = useState(false) // 필터 변경 감지
  
  // 스트리밍 관련 상태 (트렌딩용)
  const [useStreamMode, setUseStreamMode] = useState(true) // 스트리밍 모드 사용 여부
  const [streamingProgress, setStreamingProgress] = useState<{completed: number, total: number, percentage: number} | null>(null)
  const [streamingBySource, setStreamingBySource] = useState<{[key: string]: NewsArticle[]}>({})
  const [streamingActiveSources, setStreamingActiveSources] = useState<string[]>([])
  const [streamingMessages, setStreamingMessages] = useState<string[]>([])
  const [isStreamingComplete, setIsStreamingComplete] = useState(false)

  // 검색 스트리밍 관련 상태
  const [useSearchStreamMode, setUseSearchStreamMode] = useState(true) // 검색 스트리밍 모드 사용 여부
  const [searchStreamingProgress, setSearchStreamingProgress] = useState<{completed: number, total: number, percentage: number} | null>(null)
  const [searchStreamingBySource, setSearchStreamingBySource] = useState<{[key: string]: NewsArticle[]}>({})
  const [searchStreamingMessages, setSearchStreamingMessages] = useState<string[]>([])
  const [isSearchStreamingComplete, setIsSearchStreamingComplete] = useState(false)

  // 뉴스 사이트 목록 및 체크박스 상태
  const newsSites = [
    { id: 'bbc', name: 'BBC News', icon: '🇬🇧', isSlow: false },
    { id: 'thesun', name: 'The Sun', icon: '☀️', isSlow: false },
    { id: 'nypost', name: 'NY Post', icon: '🗞️', isSlow: true },
    { id: 'dailymail', name: 'Daily Mail', icon: '📧', isSlow: true },
    { id: 'scmp', name: 'SCMP', icon: '🇭🇰', isSlow: true },
    { id: 'vnexpress', name: 'VN Express', icon: '🇻🇳', isSlow: false },
    { id: 'bangkokpost', name: 'Bangkok Post', icon: '🇹🇭', isSlow: false },
    { id: 'asahi', name: 'Asahi Shimbun', icon: '🇯🇵', isSlow: false },
    { id: 'yomiuri', name: 'Yomiuri Shimbun', icon: '📰', isSlow: false }
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

  // 컴포넌트 마운트 시에만 초기 로드
  useEffect(() => {
    loadTrendingNews('all')
  }, []) // 빈 dependency로 초기 마운트 시에만 실행

  // 자동 새로고침 타이머 (selectedCategory 변경과 분리)
  useEffect(() => {
    const autoRefreshInterval = setInterval(() => {
      if (showTrending && viewMode === 'trending') {
        loadTrendingNews(selectedCategory)
        console.log('트렌딩 뉴스 자동 업데이트')
      }
    }, 30 * 60 * 1000) // 30분 = 30 * 60 * 1000 밀리초
    
    // 컴포넌트 언마운트 시 타이머 정리
    return () => {
      clearInterval(autoRefreshInterval)
    }
  }, [showTrending, selectedCategory, viewMode])

  // 수동 새로고침 함수
  const refreshTrendingNews = () => {
    loadTrendingNews(selectedCategory)
  }

  // 카테고리 변경 핸들러
  const handleCategoryChange = (categoryId: string) => {
    // 스트리밍 상태 완전 초기화
    setStreamingBySource({})
    setStreamingActiveSources([])
    setStreamingMessages([])
    setStreamingProgress(null)
    setIsStreamingComplete(false)
    setTrendingNews(null) // 기존 일반 모드 결과도 초기화
    
    // 새 카테고리로 로드
    loadTrendingNews(categoryId)
  }

  const loadTrendingNews = async (category: string = 'all') => {
    if (useStreamMode) {
      loadTrendingNewsStream(category)
    } else {
      setTrendingLoading(true)
      try {
        const sourcesParam = getSelectedSourcesString()
        const result = await getTrendingNews(category, 10, sourcesParam) // limit을 10개로 증가
        setTrendingNews(result)
        setSelectedCategory(category)
      } catch (error) {
        console.error('트렌딩 뉴스 로드 실패:', error)
      } finally {
        setTrendingLoading(false)
      }
    }
  }

  // 스트리밍 트렌딩 뉴스 로드
  const loadTrendingNewsStream = async (category: string = 'all') => {
    setTrendingLoading(true)
    setStreamingProgress(null)
    setStreamingBySource({})
    setStreamingActiveSources([])
    setStreamingMessages([]) // 완전히 초기화
    setIsStreamingComplete(false)
    setSelectedCategory(category)
    
    // 이전 스트리밍이 있다면 잠시 대기
    await new Promise(resolve => setTimeout(resolve, 100))
    
    const sourcesParam = getSelectedSourcesString()
    
    try {
      await getTrendingNewsStream(
        category,
        10, // 사이트당 10개씩으로 증가
        sourcesParam,
        // onMessage 콜백
        (message: StreamingMessage) => {
          console.log('스트리밍 메시지:', message)
          
          switch (message.type) {
            case 'start':
              setStreamingMessages(prev => [...prev, `🚀 트렌딩 뉴스 검색 시작 (카테고리: ${message.category})`])
              break
              
            case 'source_complete':
              if (message.source && message.articles) {
                setStreamingBySource(prev => ({
                  ...prev,
                  [message.source as string]: message.articles || []
                }))
                setStreamingActiveSources(prev => [...prev, message.source as string])
                setStreamingMessages(prev => [...prev, `✅ ${message.source}: ${message.article_count}개 기사`])
              }
              if (message.progress) {
                setStreamingProgress(message.progress)
              }
              break
              
            case 'source_empty':
              if (message.source) {
                setStreamingMessages(prev => [...prev, `⚪ ${message.source}: 결과 없음`])
              }
              if (message.progress) {
                setStreamingProgress(message.progress)
              }
              break
              
            case 'source_timeout':
              if (message.source) {
                setStreamingMessages(prev => [...prev, `⏰ ${message.source}: 타임아웃`])
              }
              if (message.progress) {
                setStreamingProgress(message.progress)
              }
              break
              
            case 'source_error':
              if (message.source) {
                setStreamingMessages(prev => [...prev, `❌ ${message.source}: 오류 발생`])
              }
              if (message.progress) {
                setStreamingProgress(message.progress)
              }
              break
              
            case 'complete':
              setStreamingMessages(prev => [...prev, `🎉 모든 사이트 완료! 총 ${message.total_completed}개 기사`])
              break
              
            case 'error':
              setStreamingMessages(prev => [...prev, `💥 오류: ${message.message}`])
              break
          }
        },
        // onError 콜백
        (error: Error) => {
          console.error('스트리밍 오류:', error)
          setStreamingMessages(prev => [...prev, `💥 스트리밍 오류: ${error.message}`])
          setTrendingLoading(false)
        },
        // onComplete 콜백
        () => {
          console.log('스트리밍 완료')
          setTrendingLoading(false)
          setIsStreamingComplete(true)
        }
      )
    } catch (error) {
      console.error('스트리밍 시작 실패:', error)
      setStreamingMessages(prev => [...prev, `💥 스트리밍 시작 실패: ${error}`])
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
    if (useSearchStreamMode) {
      await handleSearchStream(searchQuery, page)
    } else {
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
          10, // 각 사이트에서 10개씩
          sourcesParam, // 선택된 사이트들만
          sortOption, // 선택된 정렬 방식
          dateFrom || undefined,
          dateTo || undefined,
          groupBySource // 출처별 그룹핑 옵션 전달
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
  }

  const handleSearchStream = async (searchQuery: string, page: number = 1) => {
    setLoading(true)
    if (page === 1) {
      setQuery(searchQuery)
      setCurrentPage(1)
    }
    
    // 검색 스트리밍 상태 초기화
    setSearchStreamingBySource({})
    setSearchStreamingMessages([])
    setSearchStreamingProgress(null)
    setIsSearchStreamingComplete(false)
    setSearchResult(null)
    
    // 이전 스트리밍이 있다면 잠시 대기
    await new Promise(resolve => setTimeout(resolve, 100))
    
    const sourcesParam = getSelectedSourcesString()
    
    try {
      await searchNewsStream(
        searchQuery,
        page,
        10, // 사이트당 10개씩
        sourcesParam,
        sortOption, // 선택된 정렬 방식
        // onMessage 콜백
        (message: SearchStreamingMessage) => {
          console.log('검색 스트리밍 메시지:', message)
          
          switch (message.type) {
            case 'start':
              setSearchStreamingMessages(prev => [...prev, `🔍 뉴스 검색 시작: "${message.query}"`])
              break
              
            case 'source_complete':
              if (message.source && message.articles) {
                setSearchStreamingBySource(prev => ({
                  ...prev,
                  [message.source as string]: message.articles || []
                }))
                setSearchStreamingMessages(prev => [...prev, `✅ ${message.source}: ${message.article_count}개 기사`])
              }
              if (message.progress) {
                setSearchStreamingProgress(message.progress)
              }
              break
              
            case 'source_empty':
              if (message.source) {
                setSearchStreamingMessages(prev => [...prev, `⚪ ${message.source}: 검색 결과 없음`])
              }
              if (message.progress) {
                setSearchStreamingProgress(message.progress)
              }
              break
              
            case 'source_timeout':
              if (message.source) {
                setSearchStreamingMessages(prev => [...prev, `⏰ ${message.source}: 타임아웃`])
              }
              if (message.progress) {
                setSearchStreamingProgress(message.progress)
              }
              break
              
            case 'source_error':
              if (message.source) {
                setSearchStreamingMessages(prev => [...prev, `❌ ${message.source}: 오류 발생`])
              }
              if (message.progress) {
                setSearchStreamingProgress(message.progress)
              }
              break
              
            case 'complete':
              setSearchStreamingMessages(prev => [...prev, `🎉 검색 완료! 총 ${message.total_articles}개 기사`])
              setIsSearchStreamingComplete(true)
              break
              
            case 'error':
              setSearchStreamingMessages(prev => [...prev, `💥 오류: ${message.message}`])
              break
          }
        },
        // onError 콜백
        (error: Error) => {
          console.error('검색 스트리밍 오류:', error)
          setSearchStreamingMessages(prev => [...prev, `💥 검색 스트리밍 오류: ${error.message}`])
          setLoading(false)
        },
        // onComplete 콜백
        () => {
          console.log('검색 스트리밍 완료')
          setLoading(false)
          setIsSearchStreamingComplete(true)
        }
      )
    } catch (error) {
      console.error('검색 스트리밍 실패:', error)
      setSearchStreamingMessages(prev => [...prev, `💥 검색 스트리밍 실패: ${error}`])
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



  // 트렌딩으로 돌아가기
  const goBackToTrending = () => {
    setViewMode('trending')
    setSearchResult(null)
    setQuery('')
    setCurrentPage(1)
    setSearchStreamingBySource({})
    if (!trendingNews) {
      loadTrendingNews(selectedCategory)
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
      {/* 토글 버튼 */}
      <div className="bg-gray-50 p-4 rounded-lg">
        <div className="flex items-center justify-center space-x-4">
          <button
            onClick={() => {
              setViewMode('trending')
              setQuery('')
              setSearchResult(null)
              setCurrentPage(1)
              // 검색 스트리밍 상태 완전 초기화
              setSearchStreamingBySource({})
              setSearchStreamingMessages([])
              setSearchStreamingProgress(null)
              setIsSearchStreamingComplete(false)
              // 트렌딩 스트리밍 상태 완전 초기화
              setStreamingBySource({})
              setStreamingMessages([])
              setStreamingProgress(null)
              setIsStreamingComplete(false)
              setShowTrending(true)
              // 잠시 대기 후 로드 (상태 초기화 완료 후)
              setTimeout(() => {
                loadTrendingNews(selectedCategory)
              }, 50)
            }}
            className={`px-6 py-3 rounded-lg font-medium transition-colors ${
              viewMode === 'trending'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            🔥 트렌딩 뉴스
          </button>
          <button
            onClick={() => {
              setViewMode('search')
              setShowTrending(false)
              // 트렌딩 스트리밍 상태 완전 초기화
              setStreamingBySource({})
              setStreamingMessages([])
              setStreamingProgress(null)
              setIsStreamingComplete(false)
              setTrendingLoading(false)
            }}
            className={`px-6 py-3 rounded-lg font-medium transition-colors ${
              viewMode === 'search'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            🔍 뉴스 검색
          </button>
        </div>
      </div>

      {/* 검색 섹션 */}
      {viewMode === 'search' && (
        <div className="space-y-6">
          <div className="text-center">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">
              글로벌 뉴스 검색
            </h2>
            <p className="text-gray-600 mb-6">
              9개 글로벌 뉴스 사이트에서 실시간으로 뉴스를 검색하세요
            </p>
          </div>
        
          {/* 메인 검색 레이아웃: 왼쪽 필터 + 오른쪽 검색/결과 */}
          <div className="flex flex-col lg:flex-row gap-6 max-w-7xl mx-auto">
            {/* 왼쪽 사이드바: 모든 필터들 */}
            <div className="w-full lg:w-80 flex-shrink-0 space-y-4">
              
              {/* 스트리밍 모드 토글 */}
              <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-4 border border-blue-200">
                <h4 className="font-semibold text-gray-800 text-sm mb-3 flex items-center">
                  ⚡ 검색 모드
                </h4>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={useSearchStreamMode}
                    onChange={(e) => setUseSearchStreamMode(e.target.checked)}
                    className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus:ring-2"
                  />
                  <span className="text-sm text-gray-700">
                    스트리밍 모드 (실시간 업데이트)
                  </span>
                </label>
                <p className="text-xs text-gray-500 mt-2">
                  스트리밍 모드에서는 검색 결과가 실시간으로 업데이트됩니다.
                </p>
              </div>

              {/* 뉴스 사이트 선택 */}
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-semibold text-gray-800 text-sm">📰 뉴스 사이트 선택</h4>
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
                  <div className="space-y-1 max-h-60 overflow-y-auto">
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
                        <span className="text-sm text-gray-700 flex items-center flex-1">
                          <span className="mr-1">{site.icon}</span>
                          {site.name}
                          {site.isSlow && (
                            <span className="ml-2 px-1.5 py-0.5 bg-orange-100 text-orange-600 text-xs rounded font-medium">
                              느림
                            </span>
                          )}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>

              {/* 정렬 및 그룹핑 옵션 */}
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <h4 className="font-semibold text-gray-800 text-sm mb-3">🔄 정렬 및 표시</h4>
                
                {/* 정렬 선택 */}
                <div className="space-y-3">
                  <div>
                    <label htmlFor="sort-select" className="text-xs font-medium text-gray-600 block mb-1">
                      정렬 방식:
                    </label>
                    <select
                      id="sort-select"
                      value={sortOption}
                      onChange={(e) => {
                        setSortOption(e.target.value)
                        if (query) {
                          handleSearch(query, 1) // 정렬 변경 시 첫 페이지로 돌아감
                        }
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="date_desc">📅 최신순</option>
                      <option value="date_asc">📅 오래된순</option>
                      <option value="relevance">🎯 관련도순</option>
                    </select>
                  </div>
                  
                  {/* 그룹핑 토글 */}
                  <div>
                    <label className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={groupBySource}
                        onChange={(e) => {
                          const newGroupBySource = e.target.checked
                          setGroupBySource(newGroupBySource)
                          if (query) {
                            // 그룹핑 옵션 변경 후 즉시 다시 검색
                            handleSearch(query, 1)
                          }
                        }}
                        className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus:ring-2"
                      />
                      <span className="text-sm text-gray-700">
                        📑 출처별 그룹핑
                      </span>
                    </label>
                  </div>
                </div>
              </div>

              {/* 날짜 범위 필터 */}
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-semibold text-gray-800 text-sm">📅 날짜 범위 필터</h4>
                  <button
                    onClick={() => setShowDateFilter(!showDateFilter)}
                    className="text-xs text-blue-600 hover:text-blue-800"
                  >
                    {showDateFilter ? '숨기기' : '표시'}
                  </button>
                </div>
                
                {showDateFilter && (
                  <div className="space-y-3">
                    <div>
                      <label htmlFor="date-from" className="text-xs font-medium text-gray-600 block mb-1">
                        시작 날짜:
                      </label>
                      <input
                        id="date-from"
                        type="datetime-local"
                        value={dateFrom}
                        onChange={(e) => setDateFrom(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    
                    <div>
                      <label htmlFor="date-to" className="text-xs font-medium text-gray-600 block mb-1">
                        종료 날짜:
                      </label>
                      <input
                        id="date-to"
                        type="datetime-local"
                        value={dateTo}
                        onChange={(e) => setDateTo(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    
                    <div className="flex space-x-2">
                      <button
                        onClick={() => query && handleSearch(query, 1)}
                        className="flex-1 px-3 py-2 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 transition-colors"
                      >
                        적용
                      </button>
                      <button
                        onClick={resetDateFilter}
                        className="flex-1 px-3 py-2 bg-gray-500 text-white rounded text-sm hover:bg-gray-600 transition-colors"
                      >
                        초기화
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* 활성 필터 표시 */}
              {(dateFrom || dateTo || sortOption !== 'date_desc') && (
                <div className="bg-blue-50 rounded-lg p-3 border border-blue-200">
                  <h4 className="font-semibold text-blue-800 text-sm mb-2">🔍 활성 필터</h4>
                  <div className="space-y-1">
                    {(dateFrom || dateTo) && (
                      <div className="flex items-center justify-between px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs">
                        <span>
                          📅 날짜: 
                          {dateFrom && ` ${dateFrom.replace('T', ' ')}부터`}
                          {dateTo && ` ${dateTo.replace('T', ' ')}까지`}
                        </span>
                        <button
                          onClick={resetDateFilter}
                          className="text-red-500 hover:text-red-700 ml-1"
                        >
                          ✕
                        </button>
                      </div>
                    )}
                    
                    {sortOption !== 'date_desc' && (
                      <div className="flex items-center justify-between px-2 py-1 bg-green-100 text-green-700 rounded text-xs">
                        <span>
                          {sortOption === 'date_asc' ? '📅 오래된순' : 
                           sortOption === 'relevance' ? '🎯 관련도순' : ''}
                        </span>
                        <button
                          onClick={() => {
                            setSortOption('date_desc')
                            if (query) handleSearch(query, 1)
                          }}
                          className="text-red-500 hover:text-red-700 ml-1"
                        >
                          ✕
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
            
            {/* 오른쪽 메인 콘텐츠: 검색창 + 결과 */}
            <div className="flex-1 space-y-6">
              {/* 검색창 */}
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <SearchBar onSearch={(query) => handleSearch(query)} loading={loading} />
              </div>
              
              {/* 검색 결과 또는 스트리밍 결과 표시 영역 */}
              <div className="min-h-[400px]">
                {/* 검색 스트리밍 결과 */}
                {useSearchStreamMode && Object.keys(searchStreamingBySource).length > 0 ? (
                  <div className="space-y-6">
                    {/* 검색 스트리밍 헤더 */}
                    <div className="bg-gray-50 p-4 rounded-lg border">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="flex items-center space-x-3 mb-2">
                            <h3 className="text-lg font-semibold text-gray-800">
                              🔍 검색 결과 (실시간)
                            </h3>
                            <button
                              onClick={goBackToTrending}
                              className="px-3 py-1 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors"
                            >
                              📈 트렌딩으로 돌아가기
                            </button>
                          </div>
                          <div className="text-sm text-gray-600">
                            키워드: <strong>"{query}"</strong>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* 검색 스트리밍 진행률 */}
                    {searchStreamingProgress && loading && (
                      <div className="bg-green-50 p-4 rounded-lg border border-green-200">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-green-800">
                            🔍 검색 진행: {searchStreamingProgress.completed}/{searchStreamingProgress.total} 사이트
                          </span>
                          <span className="text-sm text-green-600">
                            {searchStreamingProgress.percentage}%
                          </span>
                        </div>
                        <div className="w-full bg-green-200 rounded-full h-2">
                          <div 
                            className="bg-green-600 h-2 rounded-full transition-all duration-300 ease-out"
                            style={{ width: `${searchStreamingProgress.percentage}%` }}
                          ></div>
                        </div>
                      </div>
                    )}

                    {/* 검색 스트리밍 메시지 */}
                    {searchStreamingMessages.length > 0 && (
                      <div className="bg-gray-50 p-4 rounded-lg border max-h-40 overflow-y-auto">
                        <h4 className="text-sm font-medium text-gray-800 mb-2">📊 검색 로그</h4>
                        <div className="space-y-1">
                          {searchStreamingMessages.slice(-10).map((msg, index) => (
                            <div key={index} className="text-xs text-gray-600">
                              {msg}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 스트리밍 검색 결과 (사이트별로 실시간 표시) */}
                    {Object.entries(searchStreamingBySource).map(([source, articles]) => (
                      <div key={source} className="space-y-4 animate-fade-in">
                        {/* 출처 헤더 */}
                        <div className="border-b border-gray-200 pb-2">
                          <h4 className="text-lg font-semibold text-gray-800 flex items-center">
                            <span className="w-2 h-2 bg-green-400 rounded-full mr-2 animate-pulse"></span>
                            🔍 {source}
                            <span className="ml-2 px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full">
                              {articles.length}개
                            </span>
                          </h4>
                        </div>
                        
                        {/* 출처별 기사 그리드 */}
                        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                          {articles.map((article: NewsArticle, index: number) => (
                            <NewsCard key={`${source}-search-streaming-${index}`} article={article} />
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : searchResult && searchResult.total_articles > 0 ? (
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

                    {/* 기사 표시 */}
                    {groupBySource ? (
                      // 출처별 그룹핑 표시 (백엔드에서 받은 데이터 사용)
                      <div className="space-y-8">
                        {Object.entries(searchResult.articles_by_source || {}).map(([source, articles]) => (
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
                  </div>
                ) : query && !loading ? (
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
                ) : (
                  <div className="text-center py-12 text-gray-400">
                    <p>🔍 검색어를 입력하고 엔터를 눌러주세요</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 트렌딩 뉴스 대시보드 */}
      {viewMode === 'trending' && (
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
                onClick={() => handleCategoryChange(category.id)}
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

          {/* 스트리밍 모드 토글 */}
          <div className="flex items-center justify-center mb-4">
            <label className="flex items-center space-x-2 text-sm">
              <input
                type="checkbox"
                checked={useStreamMode}
                onChange={(e) => {
                  const newStreamMode = e.target.checked
                  setUseStreamMode(newStreamMode)
                  
                  // 모드 변경 시 상태 초기화하고 현재 카테고리 다시 로드
                  if (newStreamMode) {
                    // 스트리밍 모드로 변경 시 일반 모드 결과 초기화
                    setTrendingNews(null)
                  } else {
                    // 일반 모드로 변경 시 스트리밍 상태 초기화
                    setStreamingBySource({})
                    setStreamingActiveSources([])
                    setStreamingMessages([])
                    setStreamingProgress(null)
                    setIsStreamingComplete(false)
                  }
                  
                  // 현재 선택된 카테고리로 다시 로드
                  setTimeout(() => {
                    loadTrendingNews(selectedCategory)
                  }, 100)
                }}
                className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus:ring-2"
              />
              <span className="text-gray-700">
                ⚡ 스트리밍 모드 (실시간 업데이트)
              </span>
            </label>
          </div>

                  {/* 트렌딩 뉴스 내용 */}
        {useStreamMode ? (
          // 스트리밍 모드
          <div className="space-y-6">
            {/* 스트리밍 진행률 */}
            {streamingProgress && trendingLoading && (
              <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-blue-800">
                    🔍 진행상황: {streamingProgress.completed}/{streamingProgress.total} 사이트
                  </span>
                  <span className="text-sm text-blue-600">
                    {streamingProgress.percentage}%
                  </span>
                </div>
                <div className="w-full bg-blue-200 rounded-full h-2">
                  <div 
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300 ease-out"
                    style={{ width: `${streamingProgress.percentage}%` }}
                  ></div>
                </div>
              </div>
            )}

            {/* 스트리밍 메시지 */}
            {streamingMessages.length > 0 && (
              <div className="bg-gray-50 p-4 rounded-lg border max-h-40 overflow-y-auto">
                <h4 className="text-sm font-medium text-gray-800 mb-2">📊 트렌딩 로그</h4>
                <div className="space-y-1">
                  {streamingMessages.slice(-10).map((msg, index) => (
                    <div key={index} className="text-xs text-gray-600">
                      {msg}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 스트리밍 결과 (사이트별로 실시간 표시) */}
            {Object.keys(streamingBySource).length > 0 ? (
              <div className="space-y-8">
                {Object.entries(streamingBySource).map(([source, articles]) => (
                  <div key={source} className="space-y-4 animate-fade-in">
                    {/* 출처 헤더 */}
                    <div className="border-b border-gray-200 pb-2">
                      <h4 className="text-lg font-semibold text-gray-800 flex items-center">
                        <span className="w-2 h-2 bg-green-400 rounded-full mr-2 animate-pulse"></span>
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
              </div>
            ) : trendingLoading ? (
              <div className="text-center py-8">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                <p className="mt-2 text-gray-600">스트리밍 트렌딩 뉴스 로딩 중...</p>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                카테고리를 선택하여 트렌딩 뉴스를 확인하세요.
              </div>
            )}
          </div>
        ) : trendingLoading ? (
          // 일반 모드 로딩
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

      {/* 로딩 상태 */}
      {loading && viewMode === 'search' && !useSearchStreamMode && (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="mt-2 text-gray-600">검색 중...</p>
        </div>
      )}



      {/* 초기 안내 */}
    </div>
  )
} 