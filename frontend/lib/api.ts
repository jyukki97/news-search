// 뉴스 API 타입 정의
export interface NewsArticle {
  title: string
  url: string
  summary: string
  published_date: string
  source: string
  category?: string
  scraped_at: string
  relevance_score?: number
  image_url?: string
}

export interface SearchResponse {
  success: boolean
  query: string
  page: number
  per_site_limit: number
  total_articles: number
  active_sources: string[]
  has_next_page: boolean
  group_by_source: boolean
  articles: NewsArticle[]
  articles_by_source: { [key: string]: NewsArticle[] }
}

export interface LatestNewsResponse {
  success: boolean
  category: string
  total_articles: number
  source: string
  articles: NewsArticle[]
}

export interface CategoriesResponse {
  success: boolean
  categories: string[]
  descriptions: Record<string, string>
}

export interface TrendingResponse {
  success: boolean
  category: string
  total_articles: number
  active_sources: string[]
  trending_by_source: { [key: string]: NewsArticle[] }
  last_updated: string
}

// API 기본 URL - 환경변수 사용 (기본값: localhost)
// Render 배포용 임시 하드코딩 (환경변수 문제 해결용)
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://news-search-backend-flyf.onrender.com'

// API 요청 헬퍼 함수
async function apiRequest<T>(endpoint: string, timeoutMs: number = 15000): Promise<T> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
  
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      signal: controller.signal
    })
    
    clearTimeout(timeoutId)
    
    if (!response.ok) {
      throw new Error(`API 요청 실패: ${response.status} ${response.statusText}`)
    }
    
    return response.json()
  } catch (error) {
    clearTimeout(timeoutId)
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('요청 시간이 초과되었습니다. 다시 시도해주세요.')
    }
    throw error
  }
}

// 뉴스 검색 (페이지네이션 지원)
export async function searchNews(
  query: string, 
  page: number = 1, 
  perSiteLimit: number = 10,
  sources: string = 'all',
  sort: string = 'date_desc',
  dateFrom?: string,
  dateTo?: string,
  groupBySource: boolean = false
): Promise<SearchResponse> {
  const encodedQuery = encodeURIComponent(query)
  let url = `/api/news/search?query=${encodedQuery}&page=${page}&per_site_limit=${perSiteLimit}&sources=${sources}&sort=${sort}&group_by_source=${groupBySource}`
  
  if (dateFrom) {
    url += `&date_from=${dateFrom}`
  }
  if (dateTo) {
    url += `&date_to=${dateTo}`
  }
  
  return apiRequest<SearchResponse>(url)
}

// 최신 뉴스 가져오기
export async function getLatestNews(category: string = 'top_stories', limit: number = 10): Promise<LatestNewsResponse> {
  return apiRequest<LatestNewsResponse>(`/api/news/latest?category=${category}&limit=${limit}`)
}

// 카테고리 목록 가져오기
export async function getCategories(): Promise<CategoriesResponse> {
  return apiRequest<CategoriesResponse>('/api/news/categories')
} 

// 트렌딩 뉴스 가져오기
export async function getTrendingNews(
  category: string = 'all', 
  limit: number = 2, 
  sources: string = 'all'
): Promise<TrendingResponse> {
  return apiRequest<TrendingResponse>(`/api/news/trending?category=${category}&limit=${limit}&sources=${sources}`)
}

// 스트리밍 트렌딩 뉴스 인터페이스
export interface StreamingMessage {
  type: 'start' | 'source_complete' | 'source_empty' | 'source_timeout' | 'source_error' | 'complete' | 'error'
  source?: string
  source_key?: string
  articles?: NewsArticle[]
  article_count?: number
  message?: string
  progress?: {
    completed: number
    total: number
    percentage: number
  }
  category?: string
  limit?: number
  sources?: string
  total_completed?: number
  total_articles?: number
  timestamp: string
}

// 스트리밍 트렌딩 뉴스 가져오기
export async function getTrendingNewsStream(
  category: string = 'all',
  limit: number = 2,
  sources: string = 'all',
  onMessage: (message: StreamingMessage) => void,
  onError?: (error: Error) => void,
  onComplete?: () => void
): Promise<void> {
  try {
    const url = `${API_BASE_URL}/api/news/trending/stream?category=${category}&limit=${limit}&sources=${sources}`
    
    const response = await fetch(url)
    
    if (!response.ok) {
      throw new Error(`스트리밍 요청 실패: ${response.status} ${response.statusText}`)
    }
    
    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('스트림 리더를 생성할 수 없습니다')
    }
    
    const decoder = new TextDecoder()
    let buffer = ''
    
    try {
      while (true) {
        const { done, value } = await reader.read()
        
        if (done) {
          onComplete?.()
          break
        }
        
        // 청크를 버퍼에 추가
        buffer += decoder.decode(value, { stream: true })
        
        // 완전한 메시지들을 추출
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // 마지막 불완전한 라인은 버퍼에 보관
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const jsonData = line.slice(6) // 'data: ' 제거
              if (jsonData.trim()) {
                const message: StreamingMessage = JSON.parse(jsonData)
                onMessage(message)
              }
            } catch (parseError) {
              console.warn('JSON 파싱 실패:', parseError, 'Line:', line)
            }
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
    
  } catch (error) {
    console.error('스트리밍 오류:', error)
    onError?.(error instanceof Error ? error : new Error('알 수 없는 오류가 발생했습니다'))
  }
} 

// 스트리밍 검색 인터페이스
export interface SearchStreamingMessage {
  type: 'start' | 'source_complete' | 'source_empty' | 'source_timeout' | 'source_error' | 'complete' | 'error'
  source?: string
  source_key?: string
  articles?: NewsArticle[]
  article_count?: number
  message?: string
  progress?: {
    completed: number
    total: number
    percentage: number
  }
  query?: string
  page?: number
  per_site_limit?: number
  sources?: string
  sort?: string
  total_completed?: number
  total_articles?: number
  timestamp: string
}

// 스트리밍 검색 API
export async function searchNewsStream(
  query: string,
  page: number = 1,
  per_site_limit: number = 10,
  sources: string = 'all',
  sort: string = 'date_desc',
  onMessage: (message: SearchStreamingMessage) => void,
  onError?: (error: Error) => void,
  onComplete?: () => void
): Promise<void> {
  try {
    const url = `${API_BASE_URL}/api/news/search/stream?query=${encodeURIComponent(query)}&page=${page}&per_site_limit=${per_site_limit}&sources=${sources}&sort=${sort}`
    
    const response = await fetch(url)
    
    if (!response.ok) {
      throw new Error(`스트리밍 검색 요청 실패: ${response.status} ${response.statusText}`)
    }
    
    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('스트림 리더를 생성할 수 없습니다')
    }
    
    const decoder = new TextDecoder()
    let buffer = ''
    
    try {
      while (true) {
        const { done, value } = await reader.read()
        
        if (done) {
          onComplete?.()
          break
        }
        
        // 청크를 버퍼에 추가
        buffer += decoder.decode(value, { stream: true })
        
        // 완전한 메시지들을 추출
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // 마지막 불완전한 라인은 버퍼에 보관
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const jsonData = line.slice(6) // 'data: ' 제거
              if (jsonData.trim()) {
                const message: SearchStreamingMessage = JSON.parse(jsonData)
                onMessage(message)
              }
            } catch (parseError) {
              console.warn('JSON 파싱 실패:', parseError, 'Line:', line)
            }
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
    
  } catch (error) {
    console.error('스트리밍 검색 오류:', error)
    onError?.(error instanceof Error ? error : new Error('알 수 없는 오류가 발생했습니다'))
  }
} 