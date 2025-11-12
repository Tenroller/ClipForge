import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    // Keep domain whitelist and add a remote pattern for the local backend
    domains: [
      'i.ytimg.com', // YouTube thumbnails
      'localhost', // Allow localhost for development
    ],
    // Allow images served from the backend API during local development.
    // This matches URLs like: http://localhost:9000/api/thumbnail/<file>.jpg
    remotePatterns: [
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
  // Disable private IP blocking during development
  experimental: {
    allowedRevalidateHeaderKeys: [],
    // Allow private IPs in development
    ...(process.env.NODE_ENV === 'development' && {
      allowPrivateNetworkAccess: true,
    }),
  },
};

export default nextConfig;
