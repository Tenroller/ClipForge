import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    // Keep domain whitelist and add a remote pattern for the local backend
    domains: [
      'i.ytimg.com', // YouTube thumbnails
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
    ],
  },
};

export default nextConfig;
