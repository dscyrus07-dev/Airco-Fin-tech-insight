import { NextRequest, NextResponse } from 'next/server'

// Use server-side env var for Docker internal networking
const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData()
    
    const response = await fetch(`${BACKEND_URL}/api/upload/unlock-pdf`, {
      method: 'POST',
      body: formData,
    })
    
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error unlocking PDF:', error)
    return NextResponse.json(
      { success: false, error: 'Failed to unlock PDF' },
      { status: 500 }
    )
  }
}
