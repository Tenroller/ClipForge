import { NextRequest, NextResponse } from 'next/server';

// Prefer internal Docker network URL for server-to-server calls (avoids Cloudflare roundtrip)
const BACKEND_BASE =
  process.env.API_URL ||
  (process.env.SERVICE_NAME_BACKEND ? `http://${process.env.SERVICE_NAME_BACKEND}:9000` : null) ||
  process.env.NEXT_PUBLIC_API_BASE ||
  'http://localhost:9000';

/**
 * Catch-all proxy route that forwards requests to the backend API.
 *
 * Solves cross-origin issues:
 * - Reads the first-party `auth_token` cookie and forwards it as a Bearer token
 * - Eliminates CORS preflight and CSRF cookie problems
 * - All browser API calls go through same-origin Next.js server
 */
// Allowed API path prefixes that the proxy can forward to the backend
const ALLOWED_PATH_PREFIXES = [
  '/api/',
];

async function handler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;

  // Validate path segments: reject traversal attempts and encoded tricks
  for (const segment of path) {
    if (segment === '..' || segment === '.' || segment.includes('/') || segment.includes('\\')) {
      return NextResponse.json(
        { detail: 'Invalid path' },
        { status: 400 }
      );
    }
  }

  const backendPath = '/' + path.join('/');

  // Ensure the resolved path starts with an allowed prefix
  if (!ALLOWED_PATH_PREFIXES.some((prefix) => backendPath.startsWith(prefix))) {
    return NextResponse.json(
      { detail: 'Forbidden path' },
      { status: 403 }
    );
  }

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
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60_000);

    const response = await fetch(backendUrl, {
      method: request.method,
      headers,
      body,
      signal: controller.signal,
    });

    clearTimeout(timeout);

    // Build response headers
    const responseHeaders = new Headers();
    const forwardHeaders = ['content-type', 'x-request-id', 'x-job-id'];
    for (const name of forwardHeaders) {
      const value = response.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }

    // Stream the response body to avoid buffering large payloads in memory
    if (response.body) {
      return new NextResponse(response.body, {
        status: response.status,
        headers: responseHeaders,
      });
    }

    // Fallback for responses without a body (204 No Content, etc.)
    return new NextResponse(null, {
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
