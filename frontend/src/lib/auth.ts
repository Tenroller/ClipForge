import { cookies } from 'next/headers';
import { jwtDecode } from 'jwt-decode';

// For server-side routes, prefer the internal API_URL (for Docker networking)
// Falls back to NEXT_PUBLIC_API_BASE for local development
const API_BASE = process.env.API_URL || process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:9000';

export interface User {
  username: string;
  role: string;
}

export interface JWTPayload {
  sub: string; // username
  role: string;
  exp: number;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

/**
 * Verify JWT token with backend
 */
export async function verifyToken(token: string): Promise<{ valid: boolean; user?: User }> {
  try {
    const response = await fetch(`${API_BASE}/api/auth/verify`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      cache: 'no-store',
    });

    if (!response.ok) {
      return { valid: false };
    }

    const data = await response.json();
    return {
      valid: data.valid || false,
      user: data.user,
    };
  } catch (error) {
    console.error('Token verification failed:', error);
    return { valid: false };
  }
}

/**
 * Get auth token from cookies (server-side only)
 */
export async function getAuthToken(): Promise<string | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get('auth_token');
  return token?.value || null;
}

/**
 * Get current user from token (server-side only)
 */
export async function getCurrentUser(): Promise<User | null> {
  const token = await getAuthToken();

  if (!token) {
    return null;
  }

  const verification = await verifyToken(token);

  if (!verification.valid || !verification.user) {
    return null;
  }

  return verification.user;
}

/**
 * Set auth cookie (server-side only, use in Server Actions)
 */
export async function setAuthCookie(token: string): Promise<void> {
  const cookieStore = await cookies();

  // Set HTTP-only cookie for security
  cookieStore.set('auth_token', token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 60 * 60 * 24 * 7, // 7 days
    path: '/',
  });
}

/**
 * Remove auth cookie (server-side only, use in Server Actions)
 */
export async function removeAuthCookie(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete('auth_token');
}

/**
 * Check if token is expired (can be used client or server)
 */
export function isTokenExpired(token: string): boolean {
  try {
    const decoded = jwtDecode<JWTPayload>(token);
    const currentTime = Date.now() / 1000;
    return decoded.exp < currentTime;
  } catch {
    return true;
  }
}

/**
 * Decode JWT token to get user info (can be used client or server)
 */
export function decodeToken(token: string): User | null {
  try {
    const decoded = jwtDecode<JWTPayload>(token);
    return {
      username: decoded.sub,
      role: decoded.role,
    };
  } catch {
    return null;
  }
}
