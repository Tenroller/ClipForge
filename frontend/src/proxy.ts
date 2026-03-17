import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Protected routes that require authentication
const protectedRoutes = [
  '/creator',
  '/compilations',
  '/videos',
  '/activity',
  '/cleanup',
  '/job',
  '/podcastclips',
  '/dashboard',
  '/settings',
  '/projects',
];

// Public routes that don't require authentication
const publicRoutes = ['/', '/login'];

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip API routes, static files, and other non-page routes
  // (matcher config may not be respected in all deployment modes)
  if (
    pathname.startsWith('/api') ||
    pathname.startsWith('/_next') ||
    pathname.includes('.')
  ) {
    return NextResponse.next();
  }

  // Check if route is protected
  const isProtectedRoute = protectedRoutes.some(route => pathname.startsWith(route));
  const isPublicRoute = publicRoutes.includes(pathname);

  // Get auth token from cookies
  const token = request.cookies.get('auth_token')?.value;

  // If accessing protected route without token, redirect to login
  if (isProtectedRoute && !token) {
    const url = request.nextUrl.clone();
    url.pathname = '/login';
    url.searchParams.set('redirect', pathname);
    return NextResponse.redirect(url);
  }

  // If accessing login page with valid token, redirect to creator
  if (pathname === '/login' && token) {
    const url = request.nextUrl.clone();
    url.pathname = '/creator';
    return NextResponse.redirect(url);
  }

  // For protected routes, verify token with backend
  if (isProtectedRoute && token) {
    try {
      // Prefer internal Docker network URL for server-to-server calls
      const API_BASE =
        process.env.API_URL ||
        (process.env.SERVICE_NAME_BACKEND ? `http://${process.env.SERVICE_NAME_BACKEND}:9000` : null) ||
        process.env.NEXT_PUBLIC_API_BASE ||
        'http://localhost:9000';
      const response = await fetch(`${API_BASE}/api/auth/verify`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-API-Key': 'internal-proxy',
        },
        cache: 'no-store',
      });

      // If token is invalid (401/403), redirect to login
      // For other errors (429, 5xx), let the request through
      if (response.status === 401 || response.status === 403) {
        const url = request.nextUrl.clone();
        url.pathname = '/login';
        url.searchParams.set('redirect', pathname);

        // Delete invalid token
        const res = NextResponse.redirect(url);
        res.cookies.delete('auth_token');
        return res;
      }

      if (response.ok) {
        const data = await response.json();

        if (!data.valid) {
          const url = request.nextUrl.clone();
          url.pathname = '/login';
          url.searchParams.set('redirect', pathname);

          // Delete invalid token
          const res = NextResponse.redirect(url);
          res.cookies.delete('auth_token');
          return res;
        }
      }
    } catch (error) {
      console.error('Token verification failed in middleware:', error);
      // On error, let the request through but the page will handle auth
      // This prevents blocking access if backend is temporarily down
    }
  }

  return NextResponse.next();
}

// Configure middleware to run on specific paths
export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public files (images, etc.)
     */
    '/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
