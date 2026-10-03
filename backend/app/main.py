import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api import routes

app = FastAPI(
    title="NewBody Content Auditor",
    version="0.1.0",
    description="Compare Instagram content across multiple accounts",
)

# CORS configuration
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes FIRST (so /api/* is never intercepted)
app.include_router(routes.router)

# Serve frontend static files if available
frontend_dist = Path(os.getenv("FRONTEND_DIST", "frontend/dist"))
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    # SPA fallback: serve index.html for non-API routes
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve index.html for SPA routing (except /api routes)"""
        if full_path.startswith("api/"):
            # Should not reach here (API handled by router), but just in case
            return {"error": "Not Found"}, 404

        # Try to serve requested file from dist
        requested_file = frontend_dist / full_path
        if requested_file.exists() and requested_file.is_file():
            return FileResponse(requested_file)

        # Fall back to index.html for SPA routing
        index_html = frontend_dist / "index.html"
        if index_html.exists():
            return FileResponse(index_html)

        return {"error": "Not Found"}, 404
