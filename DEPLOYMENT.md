# NewBody Content Auditor - Deployment Guide

## Render Deployment

This project is configured for deployment as a single Web Service on Render.

### Architecture

```
Render Web Service (Single)
├── FastAPI + Uvicorn (backend)
├── React + Vite (served by FastAPI)
└── Chromium (Playwright)
```

### Configuration

**Environment Variables (Render):**

| Variable | Value | Purpose |
|----------|-------|---------|
| `BROWSER_HEADLESS` | `true` | Run Chromium in headless mode |
| `FRONTEND_DIST` | `/app/frontend/dist` | Frontend build location |
| `EXPORT_DIR` | `/tmp/newbody-exports` | Excel exports (ephemeral) |
| `PORT` | `10000` | Service port |
| `CORS_ORIGINS` | Your Render URL | CORS configuration |

### Deployment Files

- **Dockerfile**: Multi-stage build (frontend → runtime)
- **.dockerignore**: Excludes unnecessary files from image
- **render.yaml**: Render Blueprint configuration
- **Health Check**: `/api/health` endpoint

### Single URL

Frontend and API are served from the same domain:

```
https://newbody-content-auditor.onrender.com/
├── / → React frontend
├── /assets/* → Vite static files
├── /api/health → Health check
├── /api/scans → Main API endpoint
└── /api/scans/{id}/export → Excel download
```

### Local Testing

Build and test locally:

```bash
# Frontend
cd frontend
npm run type-check
npm run build

# Backend
cd backend
python -m pytest -q
python -m compileall app tests

# Docker (if available)
cd ..
docker build -t newbody-content-auditor .
docker run --rm -p 10000:10000 \
  -e PORT=10000 \
  -e BROWSER_HEADLESS=true \
  newbody-content-auditor
```

Then visit: http://localhost:10000/

### Features

- ✅ React frontend served by FastAPI
- ✅ No separate frontend service needed
- ✅ SPA routing (index.html fallback)
- ✅ Health check for Render
- ✅ Chromium in headless mode
- ✅ Ephemeral exports (no persistent disk)
- ✅ Batch scanning with retry logic
- ✅ Production-ready logging

### No Additional Services Needed

- No separate database
- No Redis cache
- No frontend-only service
- No persistent storage

Everything runs in a single Render Web Service.
