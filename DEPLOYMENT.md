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

---

## Meta Graph API Configuration (Production)

### Overview

The application supports two Instagram data sources:

| Provider | Status | Method | Reliability |
|----------|--------|--------|-------------|
| **Browser** (Playwright) | Experimental | Scraping | Low (rate limit, anti-bot) |
| **Meta** (Graph API) | **Production** | Official API | High (reliable history, pagination) |

### Enabling Meta Provider

Set the following environment variables in Render:

| Variable | Required | Example | Notes |
|----------|----------|---------|-------|
| `INSTAGRAM_PROVIDER` | Yes | `meta` | Switch provider: `meta` or `browser` |
| `META_ACCESS_TOKEN` | Yes | (see below) | **SECRET** - API access token |
| `META_IG_USER_ID` | Yes | `123456789` | Instagram Professional Account ID |
| `META_GRAPH_API_VERSION` | Yes | `<version>` | Graph API version configured for your Meta app |
| `META_MAX_PAGES` | No | `100` | Max pages to fetch (default: 100) |

### Getting Meta Credentials

1. **Create Facebook App** (if not exists):
   - Go to [developers.facebook.com](https://developers.facebook.com)
   - Create a Business App
   - Add "Instagram Graph API" product

2. **Configure App Permissions**:
   - In App Roles → Add Test Users or configure Admin
   - Required scopes:
     - `instagram_basic` - Basic Instagram access
     - `pages_read_engagement` - Read page engagement data
     - `pages_show_list` - List managed pages during setup
   - Additional scopes may be required after App Review (depends on your use case)

3. **Get Long-Lived User Access Token**:
   - Use Graph API Explorer: [developers.facebook.com/tools/explorer](https://developers.facebook.com/tools/explorer)
   - Select your app and user
   - Generate User Access Token with above scopes
   - Generate a long-lived token from the short-lived one (exchange endpoint)

4. **Get Instagram Professional Account ID**:
   - Query: `GET /me/accounts?fields=name,access_token,instagram_business_account`
   - Use the long-lived User Access Token
   - From response, extract:
     - `instagram_business_account.id` → this is `META_IG_USER_ID`
     - `access_token` → this is the `META_ACCESS_TOKEN`

### Environment Variables (Render)

**Add to Render Dashboard → Environment:**

```
INSTAGRAM_PROVIDER=meta
META_ACCESS_TOKEN=<your_long_lived_access_token>
META_IG_USER_ID=<instagram_professional_account_id>
META_GRAPH_API_VERSION=<version_configured_for_your_meta_app>
META_MAX_PAGES=100
BROWSER_HEADLESS=true
FRONTEND_DIST=/app/frontend/dist
EXPORT_DIR=/tmp/newbody-exports
PORT=10000
CORS_ORIGINS=<your_render_url>
```

### Security

⚠️ **IMPORTANT:**

- `META_ACCESS_TOKEN` is a **SECRET**
  - Never commit to repository
  - Never log (application filters this automatically)
  - Treat as production credential
  - Rotate periodically

- The application:
  - ✅ Stores token only in environment
  - ✅ Never includes token in API responses
  - ✅ Never logs token value
  - ✅ Validates token on startup
  - ❌ Does NOT fallback silently to Browser if Meta misconfigured

### Advantages of Meta Provider

- **Reliable Historical Data**: Fetches complete post history with accurate dates
- **API Rate Limits**: Respects Meta Graph API rate limits (more stable than scraping)
- **Cursor Pagination**: Gets up to 50 posts per request with pagination support
- **No Login Required**: Access public professional accounts without Instagram credentials
- **Official Support**: Uses Meta Graph API, not scraping workaround

### Fallback Strategy

If `INSTAGRAM_PROVIDER` is set to `meta` but credentials missing:
- Application **fails loudly** at startup
- Error message clearly indicates misconfiguration
- No silent fallback to Browser provider
- This prevents "works in dev, fails in prod" scenarios

To use Browser provider, explicitly set:
```
INSTAGRAM_PROVIDER=browser
```

### Monitoring

Check Meta configuration with:

```bash
GET /api/meta/diagnostic
```

Returns:
```json
{
  "configured": true,
  "provider": "meta",
  "api_reachable": true,
  "source_ig_user_id_present": true
}
```

With optional username test:

```bash
GET /api/meta/diagnostic?username=newbodycol
```

Returns sample posts + accessibility status (token never exposed).

### Troubleshooting

**"Meta Instagram API no está configurada"**
- Verify `META_ACCESS_TOKEN` is set in Render
- Verify `META_IG_USER_ID` is set in Render
- Check token is not expired

**"Target account ... not found or not accessible"**
- Target account must be a Professional (Business/Creator) Account on Instagram
- Source account (authenticated with token) must be a properly configured Professional Account
- Business Discovery queries public professional accounts (no special relationship required)
- Check account is not private or restricted

**"Invalid OAuth access token" (error 190)**
- Token expired: generate new long-lived User Access Token
- Token revoked: regenerate in app settings
- Verify token is for the correct user and app

**"Permission denied" (error 10)**
- Token missing required scopes (`instagram_basic`, `pages_read_engagement`)
- Regenerate User Access Token with correct permissions from Graph API Explorer
- Verify app has Instagram Graph API product enabled
