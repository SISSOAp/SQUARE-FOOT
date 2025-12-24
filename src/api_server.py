from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

# =========================================================
# App
# =========================================================
app = FastAPI(title="SQUARE FOOT", version="1.6")

# =========================================================
# Paths (ajustados para repo raiz)
# =========================================================
# Este arquivo: .../src/api_server.py
BASE_DIR = Path(__file__).resolve().parent          # .../src
ROOT_DIR = BASE_DIR.parent                          # .../ (raiz do repo)
WEB_DIR = ROOT_DIR / "web"                          # .../web

INDEX_HTML = WEB_DIR / "index.html"
APP_JS = WEB_DIR / "app.js"
SW_JS = WEB_DIR / "sw.js"

ICONS_DIR = WEB_DIR / "icons"
DATA_DIR = WEB_DIR / "data"

# =========================================================
# Static mounts
# =========================================================
# /icons/...
if ICONS_DIR.exists():
    app.mount("/icons", StaticFiles(directory=str(ICONS_DIR)), name="icons")

# /data/...
if DATA_DIR.exists():
    app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")

# =========================================================
# Frontend entrypoints
# =========================================================
@app.get("/")
def home():
    if INDEX_HTML.exists():
        return FileResponse(str(INDEX_HTML), media_type="text/html")
    return JSONResponse({"detail": "index.html not found in /web"}, status_code=404)

@app.get("/app.js")
def serve_app_js():
    if APP_JS.exists():
        return FileResponse(str(APP_JS), media_type="application/javascript")
    return JSONResponse({"detail": "app.js not found in /web"}, status_code=404)

@app.get("/sw.js")
def serve_sw_js():
    if SW_JS.exists():
        return FileResponse(str(SW_JS), media_type="application/javascript")
    return JSONResponse({"detail": "sw.js not found in /web"}, status_code=404)

# =========================================================
# API endpoints
# =========================================================
# Observação: eu não tenho aqui o seu código completo das rotas reais
# (/leagues, /matches, /card etc). Então:
# - Se essas rotas já existem em outro arquivo, mantenha lá.
# - Se elas já existiam neste mesmo api_server.py, cole elas AQUI
#   (abaixo) e remova versões duplicadas.
#
# Como você mostrou que /leagues, /matches e /card respondem 200 no Render,
# eu vou criar apenas ALIASES para parar os 404 que estão quebrando a UI.

# Alias: /competitions -> /leagues
@app.get("/competitions")
async def competitions_alias(request: Request):
    # Se o navegador/JS chamar /competitions, redireciona para /leagues
    # (mantém querystring, se houver)
    qs = request.url.query
    url = "/leagues" + (f"?{qs}" if qs else "")
    return RedirectResponse(url=url, status_code=307)

# Alias: /predict -> /card (porque /card aparece OK no seu log)
@app.get("/predict")
async def predict_alias(request: Request):
    qs = request.url.query
    url = "/card" + (f"?{qs}" if qs else "")
    return RedirectResponse(url=url, status_code=307)

# =========================================================
# Fallback opcional para arquivos comuns do web root
# (Se você tiver links tipo /styles.css, /translation.json etc)
# =========================================================
@app.get("/{path:path}")
def web_fallback(path: str):
    # Tenta servir qualquer arquivo direto do /web (sem precisar montar tudo)
    target = WEB_DIR / path
    if target.exists() and target.is_file():
        # media_type vai no default; funciona bem para css/json/png etc
        return FileResponse(str(target))
    return JSONResponse({"detail": "Not Found"}, status_code=404)
