# Frontend Dockerfile - Vite Preview Server (Simpler than Nginx)
FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies (includes devDependencies needed for preview)
RUN npm ci

# Copy source code
COPY . .

# Build argument for API URL (can be overridden at build time)
ARG VITE_API_URL=http://localhost:9000
ENV VITE_API_URL=$VITE_API_URL

# Build the application
RUN npm run build

# Expose port (Vite preview default port)
EXPOSE 4173

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:4173 || exit 1

# Run vite preview server (config in vite.config.ts)
CMD ["npm", "run", "preview"]
