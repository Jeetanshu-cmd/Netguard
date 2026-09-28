"""
NetGuard AI — FastAPI entrypoint (api/main.py)
Run with: uvicorn api.main:app --reload --port 8000
Docs at: http://localhost:8000/docs
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.config import settings
from api.inference import model_service
from api.routes import predict, system

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("netguard.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        model_service.load()
    except FileNotFoundError as exc:
        logger.warning("Model not loaded at startup: %s", exc)
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

# Added in later branches:
#   api/ingest      -> ingest.router
#   api/websocket   -> ws.router
#   api/db-history  -> flows.router, alerts.router, stats.router
#   api/auth        -> auth.router