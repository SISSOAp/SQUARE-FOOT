# fix_staticfiles_import.py
from __future__ import annotations

from pathlib import Path
import re

PROJECT = Path(__file__).resolve().parent
API = PROJECT / "src" / "api_server.py"

IMPORT_LINE = "from fastapi.staticfiles import StaticFiles"


def backup(p: Path) -> Path:
    bak = p.with_suffix(p.suffix + ".bak")
    i = 1
    while bak.exists():
        bak = p.with_suffix(p.suffix + f".bak{i}")
        i += 1
    bak.write_bytes(p.read_bytes())
    return bak


def main():
    if not API.exists():
        print("ERRO: não encontrei", API)
        return

    text = API.read_text(encoding="utf-8", errors="ignore")
    bak = backup(API)

    # Remove qualquer import antigo de StaticFiles (pra não duplicar)
    lines = text.splitlines()
    new_lines = []
    removed_old = 0
    for ln in lines:
        if ln.strip() == IMPORT_LINE:
            removed_old += 1
            continue
        new_lines.append(ln)

    # Encontra onde inserir: ideal é logo após "from fastapi import ..."
    insert_at = 0
    for i, ln in enumerate(new_lines):
        if re.match(r"^\s*from\s+fastapi\s+import\s+.*$", ln):
            insert_at = i + 1
            break
        if re.match(r"^\s*import\s+fastapi\s*$", ln):
            insert_at = i + 1
            break

    # Se não achou, coloca após o último import do topo (antes do código)
    if insert_at == 0:
        last_import = -1
        for i, ln in enumerate(new_lines):
            if re.match(r"^\s*(from\s+\S+\s+import\s+|import\s+\S+)", ln):
                last_import = i
            else:
                # ao sair do bloco de imports, para
                if last_import != -1:
                    break
        insert_at = last_import + 1 if last_import != -1 else 0

    new_lines.insert(insert_at, IMPORT_LINE)

    API.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    print("OK: StaticFiles import garantido e posicionado no topo do arquivo.")
    print("Backup criado em:", bak)
    print("Imports antigos removidos:", removed_old)
    print("Agora rode: uvicorn src.api_server:app --reload --port 8000")


if __name__ == "__main__":
    main()
