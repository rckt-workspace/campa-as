# Stage 1: Frontend build
FROM node:20-bookworm-slim AS frontend-build

WORKDIR /frontend

# Copy package files
COPY frontend/package.json frontend/package-lock.json* ./

# Install dependencies
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# Copy frontend source
COPY frontend/src ./src
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/public ./public

# Type check and build
RUN npm run type-check
RUN npm run build

# Stage 2: Runtime
FROM python:3.11-slim-bookworm

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV BROWSER_HEADLESS=true
ENV FRONTEND_DIST=/app/frontend/dist
ENV EXPORT_DIR=/tmp/newbody-exports
ENV PORT=10000

WORKDIR /app

# Upgrade pip
RUN pip install --upgrade pip

# Copy backend
COPY backend ./backend

# Install backend dependencies
RUN pip install --no-cache-dir ./backend

# Install Playwright with Chromium
RUN python -m playwright install --with-deps chromium

# Create export directory
RUN mkdir -p ${EXPORT_DIR}

# Copy frontend dist from builder
COPY --from=frontend-build /frontend/dist ./frontend/dist

# Expose port
EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:${PORT}/api/health || exit 1

# Start server
CMD ["sh", "-c", "cd /app/backend && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
