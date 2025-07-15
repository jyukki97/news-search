'use client'

import { useState } from 'react'

interface SearchBarProps {
  onSearch: (query: string) => void
  loading?: boolean
}

export default function SearchBar({ onSearch, loading = false }: SearchBarProps) {
  const [query, setQuery] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim() && !loading) {
      onSearch(query.trim())
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value)
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl mx-auto">
      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <svg 
            className="h-5 w-5 text-gray-400" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth={2} 
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" 
            />
          </svg>
        </div>
        <input
          type="text"
          value={query}
          onChange={handleInputChange}
          placeholder="검색할 키워드를 입력하세요 (예: climate change, technology)"
          className="block w-full pl-10 pr-32 py-4 text-lg border border-gray-300 rounded-lg 
                   focus:ring-2 focus:ring-primary-500 focus:border-primary-500 
                   placeholder-gray-500 bg-white shadow-sm"
          disabled={loading}
        />
        <div className="absolute inset-y-0 right-0 flex items-center pr-3">
          <button
            type="submit"
            disabled={!query.trim() || loading}
            className="bg-primary-600 hover:bg-primary-700 disabled:bg-gray-400 
                     text-white font-medium py-2 px-6 rounded-md transition-colors
                     disabled:cursor-not-allowed flex items-center space-x-2"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                <span>검색 중...</span>
              </>
            ) : (
              <span>검색</span>
            )}
          </button>
        </div>
      </div>
      
      {/* 검색 힌트 */}
      <div className="mt-2 text-center">
        <div className="text-sm text-gray-500">
          추천 검색어: 
          {['climate change', 'technology', 'business', 'health'].map((keyword, index) => (
            <button
              key={keyword}
              onClick={() => !loading && onSearch(keyword)}
              className="ml-2 text-primary-600 hover:text-primary-700 hover:underline
                       disabled:text-gray-400 disabled:hover:no-underline"
              disabled={loading}
            >
              {keyword}
              {index < 3 && ','}
            </button>
          ))}
        </div>
      </div>
    </form>
  )
} 