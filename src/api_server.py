from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI(title="SQUARE FOOT", version="1.6")

# ========= Caminhos corretos =========
# Este arquivo fica em: <repo>/src/api_server.py
SRC_DIR = Path(__file__).resolve().parent          # <repo>/src
ROOT_DIR = SRC_DIR.parent                          # <repo>
WEB_DIR = ROOT_DIR / "web"                         # <repo>/web

# ========= Pastas estáticas =========
# /icons/...  -> <repo>/web/icons/...
# /data/...   -> <repo>/web/data/...
app.mount("/icons", StaticFiles(directory=str(WEB_DIR / "icons")), name="icons")
app.mount("/data", StaticFiles(directory=str(WEB_DIR / "data")), name="data")

# ========= Frontend (arquivos principais) =========
@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(str(WEB_DIR / "index.html"))

@app.get("/app.js", include_in_schema=False)
def serve_app_js():
    return FileResponse(str(WEB_DIR / "app.js"), media_type="application/javascript")

@app.get("/sw.js", include_in_schema=False)
def serve_sw_js():
    return FileResponse(str(WEB_DIR / "sw.js"), media_type="application/javascript")

@app.get("/styles.css", include_in_schema=False)
def serve_styles_css():
    return FileResponse(str(WEB_DIR / "styles.css"), media_type="text/css")

@app.get("/translation.json", include_in_schema=False)
def serve_translation_json():
    return FileResponse(str(WEB_DIR / "translation.json"), media_type="application/json")

@app.get("/antd.min.css", include_in_schema=False)
def serve_antd_css():
    return FileResponse(str(WEB_DIR / "antd.min.css"), media_type="text/css")

@app.get("/quill.snow.css", include_in_schema=False)
def serve_quill_css():
    return FileResponse(str(WEB_DIR / "quill.snow.css"), media_type="text/css")

# ========= Se você tiver endpoints de API (leagues/matches/card etc.) =========
# Se eles já existiam no seu api_server.py antigo, cole eles AQUI EMBAIXO,
# SEM repetir app = FastAPI(...) e SEM repetir mounts.
#
# Exemplo:
# @app.get("/leagues")
# def leagues(): ...
