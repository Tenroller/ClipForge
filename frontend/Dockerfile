# Frontend Dockerfile - React + Vite Production Build
# Multi-stage build for optimized production deployment

# ============================================================================
# Stage 1: Build the React application
# ============================================================================
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies (includes devDependencies by default)
RUN npm ci

# Copy source code
COPY . .

# Build argument for API URL (can be overridden at build time)
ARG VITE_API_URL=http://localhost:9000
ENV VITE_API_URL=$VITE_API_URL

# Build the application
RUN npm run build

# ============================================================================
# Stage 2: Serve with Nginx
# ============================================================================
FROM nginx:alpine

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Create nginx cache directory
RUN mkdir -p /var/cache/nginx

# Expose port 80
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:80/health || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
