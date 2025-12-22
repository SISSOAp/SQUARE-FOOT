# patch_icons.py
# Roda na raiz do projeto:  py .\patch_icons.py
# Faz:
#  - Insere tags de favicon/manifest no <head> do web/index.html
#  - Garante que o FastAPI sirva /icons -> web/icons no src/api_server.py
#  - Cria backups .bak antes de alterar

from pathlib import Path
import re
import sys

ICON_BLOCK = """\
<link rel="icon" href="/icons/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="16x16" href="/icons/favicon-16.png">
<link rel="icon" type="image/png" sizes="32x32" href="/icons/favicon-32.png">
<link rel="apple-touch-icon" sizes="180x180" href="/icons/icon-180.png">
<link rel="manifest" href="/icons/site.webmanifest">
<meta name="theme-color" content="#0b1723">
"""

MOUNT_BLOCK = """\
# --- icons (favicon / PWA) ---
from pathlib import Path as _Path
from fastapi.staticfiles import StaticFiles as _StaticFiles

_PROJECT_ROOT = _Path(__file__).resolve().parents[1]
_ICONS_DIR = _PROJECT_ROOT / "web" / "icons"
if _ICONS_DIR.exists():
    app.mount("/icons", _StaticFiles(directory=str(_ICONS_DIR)), name="icons")
# --- /icons ---
"""


def backup_file(p: Path) -> None:
    bak = p.with_suffix(p.suffix + ".bak")
    if not bak.exists():
        bak.write_bytes(p.read_bytes())


def patch_index_html(project_root: Path) -> None:
    html_path = project_root / "web" / "index.html"
    if not html_path.exists():
        print("ERRO: Não encontrei web/index.html")
        sys.exit(1)

    content = html_path.read_text(encoding="utf-8", errors="ignore")

    # Já tem bloco?
    if "/icons/favicon" in content and "site.webmanifest" in content:
        print(f"OK: web/index.html já parece ter tags de ícones.")
        return

    m = re.search(r"</head\s*>", content, flags=re.IGNORECASE)
    if not m:
        print("ERRO: Não encontrei </head> no web/index.html")
        sys.exit(1)

    backup_file(html_path)
    new_content = content[:m.start()] + "\n" + ICON_BLOCK + "\n" + content[m.start():]
    html_path.write_text(new_content, encoding="utf-8")
    print("OK: Tags de favicon/manifest inseridas em web/index.html")


def patch_api_server(project_root: Path) -> None:
    api_path = project_root / "src" / "api_server.py"
    if not api_path.exists():
        print("ERRO: Não encontrei src/api_server.py")
        sys.exit(1)

    text = api_path.read_text(encoding="utf-8", errors="ignore")

    # Se já tem mount de /icons, não mexe
    if re.search(r'app\.mount\(\s*["\']\/icons["\']', text):
        print("OK: src/api_server.py já tem app.mount('/icons', ...).")
        return

    # Precisa achar onde o app é criado
    lines = text.splitlines()
    app_idx = None
    for i, line in enumerate(lines):
        if re.search(r"^\s*app\s*=\s*FastAPI\s*\(", line) or re.search(r"^\s*app\s*=\s*FastAPI\s*\(\s*\)\s*$", line):
            app_idx = i
            break
        if re.search(r"^\s*app\s*=\s*FastAPI\s*$", line):
            app_idx = i
            break

    if app_idx is None:
        # fallback: procura "FastAPI()" em qualquer lugar
        for i, line in enumerate(lines):
            if "FastAPI(" in line and "app" in line and "=" in line:
                app_idx = i
                break

    if app_idx is None:
        print("ERRO: Não consegui localizar a linha de criação do app (app = FastAPI...).")
        print("Me manda as primeiras ~40 linhas do src/api_server.py que eu ajusto.")
        sys.exit(1)

    # Insere o bloco logo após a criação do app (pulando linhas vazias imediatas)
    insert_at = app_idx + 1
    while insert_at < len(lines) and lines[insert_at].strip() == "":
        insert_at += 1

    backup_file(api_path)
    lines.insert(insert_at, MOUNT_BLOCK)
    api_path.write_text("\n".join(lines) + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")
    print("OK: /icons montado em src/api_server.py (web/icons).")


def main() -> None:
    project_root = Path(__file__).resolve().parent

    # Checagem rápida: pasta web/icons existe?
    icons_dir = project_root / "web" / "icons"
    if not icons_dir.exists():
        print("AVISO: web/icons não existe ainda. Crie e gere os ícones antes.")
        print("Mas vou patchar HTML e API mesmo assim.")

    patch_index_html(project_root)
    patch_api_server(project_root)

    print("\nPróximo teste (depois de reiniciar o servidor):")
    print(" - http://127.0.0.1:8000/icons/favicon-32.png")
    print(" - http://127.0.0.1:8000/icons/site.webmanifest")
    print("\nSe abrir 200 OK e o ícone aparecer na aba, fechou.")


if __name__ == "__main__":
    main()
