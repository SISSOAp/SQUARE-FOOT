from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api import router as api_router

app = FastAPI(title="SQUARE FOOT", version="1.0")

# API
app.include_router(api_router)

# Front estático (se você servir a UI no mesmo serviço)
# Ajuste o caminho se seu HTML estiver em outro diretório.
app.mount("/", StaticFiles(directory="web", html=True), name="web")
