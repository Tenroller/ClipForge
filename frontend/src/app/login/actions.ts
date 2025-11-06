'use server';

import { redirect } from 'next/navigation';
import { setAuthCookie, removeAuthCookie, type LoginResponse } from '@/lib/auth';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:9000';

export interface LoginResult {
  success: boolean;
  error?: string;
  user?: {
    username: string;
    role: string;
  };
}

/**
 * Server Action: Login user
 */
export async function loginAction(
  username: string,
  password: string
): Promise<LoginResult> {
  try {
    const response = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, password }),
      cache: 'no-store',
    });

    if (!response.ok) {
      const error = await response.json();
      return {
        success: false,
        error: error.detail || 'Login failed. Please check your credentials.',
      };
    }

    const data: LoginResponse = await response.json();

    // Set HTTP-only cookie
    await setAuthCookie(data.access_token);

    return {
      success: true,
      user: data.user,
    };
  } catch (error) {
    console.error('Login error:', error);
    return {
      success: false,
      error: 'Network error. Please try again.',
    };
  }
}

/**
 * Server Action: Logout user
 */
export async function logoutAction(): Promise<void> {
  try {
    // Optionally call backend logout endpoint
    // (backend might log the logout event)
    // await fetch(`${API_BASE}/api/auth/logout`, {
    //   method: 'POST',
    //   headers: { 'Authorization': `Bearer ${token}` },
    // });
  } catch (error) {
    console.error('Logout error:', error);
  } finally {
    // Always remove cookie
    await removeAuthCookie();
    redirect('/login');
  }
}
