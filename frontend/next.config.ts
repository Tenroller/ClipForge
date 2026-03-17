import type { NextConfig } from "next";
import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin('./src/i18n/request.ts');

const nextConfig: NextConfig = {
  // Enable standalone output for Docker deployment
  output: 'standalone',
  images: {
    // Use remotePatterns instead of deprecated domains
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'i.ytimg.com',
        pathname: '/**',
      },
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '9000',
        pathname: '/api/thumbnail/**',
      },
      {
        protocol: 'http',
        hostname: '127.0.0.1',
        port: '9000',
        pathname: '/api/thumbnail/**',
      },
    ],
    // For local API routes
    unoptimized: process.env.NODE_ENV === 'development',
    // Allow dangerous content for development (thumbnails might be SVG/etc)
    dangerouslyAllowSVG: true,
    contentDispositionType: 'attachment',
    contentSecurityPolicy: "default-src 'self'; script-src 'none'; sandbox;",
  },
  // Remove experimental section entirely for Turbopack compatibility
  // Next.js 16 with Turbopack doesn't support many experimental features
  // Only add experimental features if they are specifically supported
};

export default withNextIntl(nextConfig);
