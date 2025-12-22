# fix_api_server.py
from __future__ import annotations

from pathlib import Path
import re

PROJECT = Path(__file__).resolve().parent
API = PROJECT / "src" / "api_server.py"

MOUNT_LINE = 'app.mount("/icons", StaticFiles(directory="web/icons"), name="icons")'

SW_ROUTE = """
@app.get("/sw.js")
def serve_sw():
    return FileResponse("web/sw.js", media_type="application/javascript")
""".strip() + "\n"


def backup(p: Path) -> Path:
    bak = p.with_suffix(p.suffix + ".bak")
    i = 1
    while bak.exists():
        bak = p.with_suffix(p.suffix + f".bak{i}")
        i += 1
    bak.write_bytes(p.read_bytes())
    return bak


def ensure_import(text: str, import_line: str, after_regex: str) -> str:
    if import_line in text:
        return text
    m = re.search(after_regex, text, flags=re.MULTILINE)
    if m:
        insert_at = m.end()
        return text[:insert_at] + "\n" + import_line + "\n" + text[insert_at:]
    return import_line + "\n" + text


def ensure_fileresponse(text: str) -> str:
    # Se já tem FileResponse em algum import, ok
    if re.search(r"\bFileResponse\b", text):
        return text

    # Se existe linha "from fastapi.responses import ...", adiciona FileResponse nela
    m = re.search(r"^(\s*from\s+fastapi\.responses\s+import\s+)(.+)$", text, flags=re.MULTILINE)
    if m:
        prefix = m.group(1)
        items = m.group(2).strip()
        # remove comentários no fim (se houver)
        items = items.split("#")[0].strip()
        parts = [p.strip() for p in items.split(",") if p.strip()]
        if "FileResponse" not in parts:
            parts.append("FileResponse")
        new_line = prefix + ", ".join(parts)
        return re.sub(r"^\s*from\s+fastapi\.responses\s+import\s+.+$", new_line, text, count=1, flags=re.MULTILINE)

    # senão, cria import novo após "from fastapi import ..."
    return ensure_import(
        text,
        "from fastapi.responses import FileResponse",
        r"^\s*from\s+fastapi\s+import\s+.*$",
    )


def main():
    if not API.exists():
        print("ERRO: não achei", API)
        return

    raw = API.read_text(encoding="utf-8", errors="ignore")
    bak = backup(API)

    # 1) Remove linhas que contenham "\1" (isso é o que está quebrando teu Python)
    lines = raw.splitlines()
    cleaned_lines = []
    removed = 0
    for ln in lines:
        if "\\1" in ln:
            removed += 1
            continue
        cleaned_lines.append(ln)
    text = "\n".join(cleaned_lines) + "\n"

    # 2) Garante imports necessários
    text = ensure_import(
        text,
        "from fastapi.staticfiles import StaticFiles",
        r"^\s*from\s+fastapi\s+import\s+.*$",
    )
    text = ensure_fileresponse(text)

    # 3) Garante mount de /icons (coloca logo depois do app = FastAPI(...))
    if MOUNT_LINE not in text:
        m = re.search(r"^\s*app\s*=\s*FastAPI\([^\)]*\)\s*$", text, flags=re.MULTILINE)
        if m:
            insert_at = m.end()
            text = text[:insert_at] + "\n" + MOUNT_LINE + "\n" + text[insert_at:]
        else:
            text += "\n" + MOUNT_LINE + "\n"

    # 4) Garante rota /sw.js
    if re.search(r'@app\.get\(\s*["\']/sw\.js["\']\s*\)', text) is None:
        # insere logo após o mount
        idx = text.find(MOUNT_LINE)
        if idx != -1:
            after = idx + len(MOUNT_LINE)
            text = text[:after] + "\n\n" + SW_ROUTE + "\n" + text[after:]
        else:
            text += "\n\n" + SW_ROUTE + "\n"

    API.write_text(text, encoding="utf-8")

    print("OK: Corrigi src/api_server.py")
    print("Backup criado em:", bak)
    print("Linhas removidas com \\\\1 :", removed)
    print("Agora rode: uvicorn src.api_server:app --reload --port 8000")


if __name__ == "__main__":
    main()
