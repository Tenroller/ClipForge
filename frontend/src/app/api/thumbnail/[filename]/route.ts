import { NextRequest, NextResponse } from 'next/server';

// For server-side routes, prefer the internal API_URL (for Docker networking)
// Falls back to NEXT_PUBLIC_API_BASE for local development
const BACKEND_BASE = process.env.API_URL || process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:9000';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ filename: string }> }
) {
  try {
    const { filename } = await params;

    // Validate filename to prevent path traversal
    if (!filename || filename.includes('..') || filename.includes('/')) {
      return new NextResponse('Invalid filename', { status: 400 });
    }

    // Fetch the thumbnail from the backend
    const backendUrl = `${BACKEND_BASE}/api/thumbnail/${filename}`;
    const response = await fetch(backendUrl);

    if (!response.ok) {
      return new NextResponse('Thumbnail not found', { status: 404 });
    }

    // Get the content type from the backend response
    const contentType = response.headers.get('content-type') || 'image/jpeg';

    // Stream the image data
    const imageData = await response.arrayBuffer();

    return new NextResponse(imageData, {
      status: 200,
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=31536000, immutable', // Cache for 1 year
      },
    });
  } catch (error) {
    console.error('Error proxying thumbnail:', error);
    return new NextResponse('Internal server error', { status: 500 });
  }
}