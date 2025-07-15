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
  articles: NewsArticle[]
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

// API 기본 URL - localhost 사용 (CORS 설정과 일치)
const API_BASE_URL = 'http://localhost:8000'

// API 요청 헬퍼 함수
async function apiRequest<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`)
  
  if (!response.ok) {
    throw new Error(`API 요청 실패: ${response.status} ${response.statusText}`)
  }
  
  return response.json()
}

// 뉴스 검색 (페이지네이션 지원)
export async function searchNews(
  query: string, 
  page: number = 1, 
  perSiteLimit: number = 3,
  sources: string = 'all',
  sort: string = 'date_desc',
  dateFrom?: string,
  dateTo?: string
): Promise<SearchResponse> {
  const encodedQuery = encodeURIComponent(query)
  let url = `/api/news/search?query=${encodedQuery}&page=${page}&per_site_limit=${perSiteLimit}&sources=${sources}&sort=${sort}`
  
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
  limit: number = 5, 
  sources: string = 'all'
): Promise<TrendingResponse> {
  return apiRequest<TrendingResponse>(`/api/news/trending?category=${category}&limit=${limit}&sources=${sources}`)
} 