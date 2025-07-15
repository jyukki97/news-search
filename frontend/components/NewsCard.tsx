import { NewsArticle } from '@/lib/api'
import Image from 'next/image'

interface NewsCardProps {
  article: NewsArticle
}

export default function NewsCard({ article }: NewsCardProps) {
  // 날짜 포맷팅
  const formatDate = (dateString: string) => {
    if (!dateString) return ''
    
    try {
      const date = new Date(dateString)
      return date.toLocaleDateString('ko-KR', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    } catch {
      return dateString
    }
  }

  // 요약 텍스트 자르기
  const truncateSummary = (text: string, maxLength: number = 150) => {
    if (!text) return ''
    if (text.length <= maxLength) return text
    return text.substring(0, maxLength) + '...'
  }

  // 카테고리 색상 매핑
  const getCategoryColor = (category: string = '') => {
    const colors: Record<string, string> = {
      'technology': 'bg-blue-100 text-blue-800',
      'business': 'bg-green-100 text-green-800',
      'health': 'bg-red-100 text-red-800',
      'science': 'bg-purple-100 text-purple-800',
      'world': 'bg-yellow-100 text-yellow-800',
      'uk': 'bg-indigo-100 text-indigo-800',
      'top_stories': 'bg-gray-100 text-gray-800'
    }
    return colors[category] || 'bg-gray-100 text-gray-800'
  }

  return (
    <article className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow 
                      border border-gray-200 overflow-hidden">
      {/* 이미지 섹션 */}
      {article.image_url && (
        <div className="relative w-full h-48">
          <Image
            src={article.image_url}
            alt={article.title}
            fill
            className="object-cover"
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
            onError={(e) => {
              // 이미지 로드 실패 시 숨기기
              const img = e.target as HTMLImageElement;
              img.style.display = 'none';
            }}
          />
        </div>
      )}
      
      <div className="p-6">
        {/* 카테고리와 출처 */}
        <div className="flex items-center justify-between mb-3">
          {article.category && (
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
                           ${getCategoryColor(article.category)}`}>
              {article.category}
            </span>
          )}
          <span className="text-sm text-gray-500 font-medium">
            {article.source}
          </span>
        </div>

        {/* 제목 */}
        <h3 className="text-lg font-semibold text-gray-900 mb-3 line-clamp-2 leading-tight">
          <a 
            href={article.url} 
            target="_blank" 
            rel="noopener noreferrer"
            className="hover:text-primary-600 transition-colors"
          >
            {article.title}
          </a>
        </h3>

        {/* 요약 */}
        {article.summary && (
          <p className="text-gray-600 text-sm mb-4 line-clamp-3">
            {truncateSummary(article.summary)}
          </p>
        )}

        {/* 하단 정보 */}
        <div className="flex items-center justify-between text-xs text-gray-500 pt-4 border-t border-gray-100">
          <time dateTime={article.published_date}>
            {formatDate(article.published_date)}
          </time>
          
          {/* 관련도 점수 (있는 경우) */}
          {article.relevance_score && (
            <div className="flex items-center">
              <span className="text-primary-600">★</span>
              <span className="ml-1">관련도 {article.relevance_score}</span>
            </div>
          )}
        </div>

        {/* 읽기 버튼 */}
        <div className="mt-4">
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center text-primary-600 hover:text-primary-700 
                     text-sm font-medium transition-colors"
          >
            <span>기사 읽기</span>
            <svg 
              className="ml-1 h-4 w-4" 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={2} 
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" 
              />
            </svg>
          </a>
        </div>
      </div>
    </article>
  )
} 