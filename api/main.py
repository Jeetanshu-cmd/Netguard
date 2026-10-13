"""
NetGuard AI — FastAPI entrypoint (api/main.py)
Run with: uvicorn api.main:app --reload --port 8000
Docs at: http://localhost:8000/docs
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from api.config import REPO_ROOT, settings
from api.inference import model_service
from api.db import init_db
from api.routes import alerts, auth, flows, predict, stats, system
from api import ws, ingest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("netguard.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        model_service.load()
    except FileNotFoundError as exc:
        logger.warning("Model not loaded at startup: %s", exc)
    try:
        init_db()
    except Exception as exc:
        logger.warning("Database init failed: %s", exc)
    yield


app = FastAPI(title="NetGuard AI API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(predict.router)
app.include_router(flows.router)
app.include_router(alerts.router)
app.include_router(stats.router)
app.include_router(ws.router)
app.include_router(ingest.router)
app.include_router(auth.router)


# --- Dashboard (README §9: in production FastAPI serves dashboard/dist) ------
# One port, one origin: no CORS and no hardcoded host, so the dashboard works
# from any device that can reach this server. SPA routes such as /alerts and
# /stats share a path with API routes, so browser page loads (Accept:
# text/html) get index.html and everything else (fetch, WebSocket) reaches the
# API untouched.
DASHBOARD_DIST = Path(REPO_ROOT / "dashboard" / "dist")
_API_DOC_PATHS = ("/docs", "/redoc", "/openapi.json", "/ws")

if (DASHBOARD_DIST / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=DASHBOARD_DIST / "assets"), name="dashboard-assets")

    @app.middleware("http")
    async def serve_dashboard_pages(request: Request, call_next):
        path = request.url.path
        if (
            request.method == "GET"
            and "text/html" in request.headers.get("accept", "")
            and not path.startswith(_API_DOC_PATHS)
        ):
            return FileResponse(DASHBOARD_DIST / "index.html")
        return await call_next(request)

    @app.get("/{path:path}", include_in_schema=False)
    def dashboard_file(path: str):
        """Root-level build files (favicon, etc.); anything else is a real 404."""
        file = (DASHBOARD_DIST / path).resolve()
        if path and file.is_file() and DASHBOARD_DIST.resolve() in file.parents:
            return FileResponse(file)
        raise HTTPException(status_code=404, detail="Not Found")
