import { NextRequest, NextResponse } from 'next/server'

export async function POST(_request: NextRequest) {
  return NextResponse.json(
    {
      message: 'Legacy password-grant login is disabled. Use the browser-based Keycloak flow instead.',
    },
    { status: 410 }
  )
}
