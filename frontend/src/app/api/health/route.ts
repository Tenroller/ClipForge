import { NextResponse } from 'next/server';

const BACKEND_BASE = process.env.API_URL || process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:9000';

export async function GET() {
  let backendStatus: 'ok' | 'unreachable' = 'unreachable';

  try {
    const res = await fetch(`${BACKEND_BASE}/api/health`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) backendStatus = 'ok';
  } catch {
    // backend unreachable
  }

  const healthy = backendStatus === 'ok';

  return NextResponse.json(
    { status: healthy ? 'ok' : 'degraded', backend: backendStatus },
    { status: healthy ? 200 : 503 }
  );
}
