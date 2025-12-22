# fix_htmlresponse_import.py
from __future__ import annotations

from pathlib import Path
import re

PROJECT = Path(__file__).resolve().parent
API = PROJECT / "src" / "api_server.py"
NEEDED = "HTMLResponse"


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

    # Se já tem HTMLResponse importado, não faz nada
    if re.search(rf"\b{NEEDED}\b", text) and re.search(r"from\s+fastapi\.responses\s+import\s+.*HTMLResponse", text):
        print("OK: HTMLResponse já está importado. Nada a fazer.")
        print("Arquivo:", API)
        return

    lines = text.splitlines()

    # 1) Tenta encontrar "from fastapi.responses import ..."
    idx = None
    for i, ln in enumerate(lines):
        if re.match(r"^\s*from\s+fastapi\.responses\s+import\s+.+", ln):
            idx = i
            break

    if idx is not None:
        ln = lines[idx]
        # Extrai itens importados
        m = re.match(r"^(\s*from\s+fastapi\.responses\s+import\s+)(.+)\s*$", ln)
        prefix, items = m.group(1), m.group(2)
        parts = [p.strip() for p in items.split(",") if p.strip()]
        if NEEDED not in parts:
            parts.append(NEEDED)
        lines[idx] = prefix + ", ".join(parts)
        API.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("OK: adicionei HTMLResponse no import existente.")
        print("Backup:", bak)
        return

    # 2) Se não existe import de responses, insere um novo perto do topo
    insert_at = 0
    for i, ln in enumerate(lines):
        if re.match(r"^\s*from\s+fastapi\s+import\s+.*$", ln) or re.match(r"^\s*import\s+fastapi\s*$", ln):
            insert_at = i + 1
            break

    lines.insert(insert_at, "from fastapi.responses import HTMLResponse")
    API.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("OK: inseri 'from fastapi.responses import HTMLResponse' no topo.")
    print("Backup:", bak)


if __name__ == "__main__":
    main()
