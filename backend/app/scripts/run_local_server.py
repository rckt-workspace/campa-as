#!/usr/bin/env python3
"""Run local development server with proper asyncio configuration"""
import os
import sys
import asyncio

# Windows asyncio event loop policy fix
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    # Get configuration from environment
    host = os.getenv("LOCAL_API_HOST", "127.0.0.1")
    port = int(os.getenv("LOCAL_API_PORT", "8005"))
    headless = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"

    print(f"Starting NewBody Content Auditor API")
    print(f"  Host: {host}")
    print(f"  Port: {port}")
    print(f"  Browser headless: {headless}")
    print(f"  Reload: disabled (use direct python execution for hot reload)")
    print()

    # Run uvicorn without reload to avoid asyncio issues
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level="info",
        reload=False,  # Never use reload in production or Windows
    )
