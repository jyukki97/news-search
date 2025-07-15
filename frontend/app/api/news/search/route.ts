import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const query = searchParams.get('query')
    const limit = searchParams.get('limit') || '10'

    console.log('API Route called with query:', query, 'limit:', limit)

    if (!query) {
      return NextResponse.json({ error: 'Query parameter is required' }, { status: 400 })
    }

    // 백엔드 API 호출
    const backendUrl = `http://localhost:8000/api/news/search?query=${encodeURIComponent(query)}&limit=${limit}`
    console.log('Calling backend URL:', backendUrl)
    
    const response = await fetch(backendUrl)
    console.log('Backend response status:', response.status)

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Backend error response:', errorText)
      throw new Error(`Backend API error: ${response.status} - ${errorText}`)
    }

    const data = await response.json()
    console.log('Backend response data:', JSON.stringify(data).substring(0, 200))
    
    return NextResponse.json(data)

  } catch (error) {
    console.error('API Proxy Error details:', error)
    return NextResponse.json(
      { 
        error: 'Failed to fetch news',
        details: error instanceof Error ? error.message : 'Unknown error'
      }, 
      { status: 500 }
    )
  }
} 