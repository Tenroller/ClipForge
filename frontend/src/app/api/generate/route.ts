import { NextRequest, NextResponse } from 'next/server';

const BACKEND_BASE = process.env.API_URL || process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:9000';

export async function POST(request: NextRequest) {
  try {
    const authToken = request.cookies.get('auth_token')?.value;

    const body = await request.json();

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-API-Key': 'internal-proxy',
    };
    if (authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    }

    const backendRes = await fetch(`${BACKEND_BASE}/api/moneyprinter/generate`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });

    const text = await backendRes.text();
    try {
      const data = JSON.parse(text);
      return NextResponse.json(data, { status: backendRes.status });
    } catch {
      return NextResponse.json(
        { detail: text || 'Backend error' },
        { status: backendRes.status }
      );
    }
  } catch (error) {
    console.error('Error proxying generate:', error);
    return NextResponse.json(
      { detail: 'Failed to start video generation' },
      { status: 502 }
    );
  }
}
