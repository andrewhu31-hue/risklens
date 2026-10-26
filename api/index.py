"""Vercel entry point: serves the FastAPI app as a Python function under /api.

vercel.json rewrites /api/* here. The app is mounted at /api (the path Vercel
passes through) and at / as a fallback, so routes resolve either way.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI  # noqa: E402

from app.main import app as risklens_app  # noqa: E402
from app.models.database import init_db  # noqa: E402

# Mounted sub-apps don't run their own lifespan, so create tables here.
init_db()

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/api", risklens_app)
app.mount("/", risklens_app)
