import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const category = searchParams.get('category') || 'top_stories'
    const limit = searchParams.get('limit') || '10'

    // 백엔드 API 호출
    const backendUrl = `http://localhost:8000/api/news/latest?category=${category}&limit=${limit}`
    const response = await fetch(backendUrl)

    if (!response.ok) {
      throw new Error(`Backend API error: ${response.status}`)
    }

    const data = await response.json()
    return NextResponse.json(data)

  } catch (error) {
    console.error('API Proxy Error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch latest news' }, 
      { status: 500 }
    )
  }
} 