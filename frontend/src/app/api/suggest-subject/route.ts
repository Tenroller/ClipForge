import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';

const BACKEND_BASE = process.env.API_URL || process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:9000';

export async function POST(request: NextRequest) {
  try {
    const cookieStore = await cookies();
    const authToken = cookieStore.get('auth_token')?.value;

    const body = await request.json();

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-API-Key': 'internal-proxy',
    };
    if (authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    }

    const response = await fetch(`${BACKEND_BASE}/api/AIvideos/suggest-subject`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Error proxying suggest-subject:', error);
    return NextResponse.json(
      { detail: 'Failed to generate subject suggestion' },
      { status: 502 }
    );
  }
}
