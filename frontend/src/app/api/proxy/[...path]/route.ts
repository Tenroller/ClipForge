import { NextRequest, NextResponse } from 'next/server';

const BACKEND_BASE = process.env.API_URL || process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:9000';

/**
 * Catch-all proxy route that forwards requests to the backend API.
 *
 * Solves cross-origin issues:
 * - Reads the first-party `auth_token` cookie and forwards it as a Bearer token
 * - Eliminates CORS preflight and CSRF cookie problems
 * - All browser API calls go through same-origin Next.js server
 */
async function handler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const backendPath = '/' + path.join('/');
  const search = request.nextUrl.search;
  const backendUrl = `${BACKEND_BASE}${backendPath}${search}`;

  // Read auth token from first-party cookie
  const authToken = request.cookies.get('auth_token')?.value;

  // Build headers for the backend request
  const headers: Record<string, string> = {
    'Content-Type': request.headers.get('content-type') || 'application/json',
    // Server-to-server requests bypass CSRF (backend exempts X-API-Key)
    'X-API-Key': 'internal-proxy',
  };

  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  // Forward the request body for non-GET methods
  let body: string | undefined;
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    body = await request.text();
  }

  try {
    const response = await fetch(backendUrl, {
      method: request.method,
      headers,
      body,
    });

    // Stream the response back
    const responseBody = await response.arrayBuffer();
    const responseHeaders = new Headers();

    // Forward relevant response headers
    const forwardHeaders = ['content-type', 'x-request-id', 'x-job-id'];
    for (const name of forwardHeaders) {
      const value = response.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }

    return new NextResponse(responseBody, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error(`Proxy error for ${request.method} ${backendPath}:`, error);
    return NextResponse.json(
      { detail: 'Backend service unavailable' },
      { status: 502 }
    );
  }
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const DELETE = handler;
export const PATCH = handler;
