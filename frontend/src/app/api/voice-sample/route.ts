import { NextRequest, NextResponse } from 'next/server';

const BACKEND_BASE = process.env.API_URL || process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:9000';

export async function GET(request: NextRequest) {
  try {
    const voice = request.nextUrl.searchParams.get('voice');
    if (!voice) {
      return new NextResponse('Missing voice parameter', { status: 400 });
    }

    const backendUrl = `${BACKEND_BASE}/api/voice-sample?voice=${encodeURIComponent(voice)}`;
    const response = await fetch(backendUrl);

    if (!response.ok) {
      return new NextResponse('Voice sample not available', { status: response.status });
    }

    const audioData = await response.arrayBuffer();
    const contentType = response.headers.get('content-type') || 'audio/wav';

    return new NextResponse(audioData, {
      status: 200,
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=86400',
      },
    });
  } catch (error) {
    console.error('Error proxying voice sample:', error);
    return new NextResponse('Internal server error', { status: 500 });
  }
}
