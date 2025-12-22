# patch_pwa.py (corrigido)
from __future__ import annotations

from pathlib import Path
import re
import sys


ICON_BLOCK = """\
<link rel="icon" href="/icons/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="16x16" href="/icons/favicon-16.png">
<link rel="icon" type="image/png" sizes="32x32" href="/icons/favicon-32.png">
<link rel="apple-touch-icon" sizes="180x180" href="/icons/icon-180.png">
<link rel="manifest" href="/icons/site.webmanifest">
<meta name="theme-color" content="#0b1220">
"""

SW_REGISTER_BLOCK = """\
<script>
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    });
  }
</script>
"""

DEFAULT_SW_JS = """\
// sw.js — Square Foot
const CACHE_NAME = "squarefoot-static-v1";
const ASSETS = [
  "/",
  "/icons/favicon.ico",
  "/icons/favicon-16.png",
  "/icons/favicon-32.png",
  "/icons/icon-180.png",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/site.webmanifest"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.map((k) => (k === CACHE_NAME ? null : caches.delete(k)))))
      .then(() => self.clients.claim())
  );
});

// Não intercepta API (pra não “congelar” estatística)
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/leagues") || url.pathname.startsWith("/matches") || url.pathname.startsWith("/card")) {
    return;
  }

  if (event.request.mode === "navigate") {
    event.respondWith(fetch(event.request).catch(() => caches.match("/")));
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((res) => {
        const copy = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return res;
      });
    })
  );
});
"""


def backup_file(p: Path) -> None:
  bak = p.with_suffix(p.suffix + ".bak")
  if not bak.exists():
    bak.write_bytes(p.read_bytes())


def patch_index_html(project_root: Path) -> None:
  html_path = project_root / "web" / "index.html"
  if not html_path.exists():
    print("ERRO: Não achei web/index.html")
    sys.exit(1)

  content = html_path.read_text(encoding="utf-8", errors="ignore")
  changed = False

  if "/icons/favicon" not in content and 'rel="manifest" href="/icons/site.webmanifest"' not in content:
    m = re.search(r"</head\s*>", content, flags=re.IGNORECASE)
    if not m:
      print("ERRO: Não encontrei </head> em web/index.html")
      sys.exit(1)
    backup_file(html_path)
    content = content[:m.start()] + ICON_BLOCK + "\n" + content[m.start():]
    changed = True
    print("OK: Ícones/manifest inseridos no <head>.")
  else:
    print("OK: web/index.html já tem ícones/manifest.")

  if "serviceWorker.register" not in content:
    m = re.search(r"</body\s*>", content, flags=re.IGNORECASE)
    backup_file(html_path)
    if m:
      content = content[:m.start()] + "\n" + SW_REGISTER_BLOCK + "\n" + content[m.start():]
    else:
      content = content + "\n" + SW_REGISTER_BLOCK + "\n"
    changed = True
    print("OK: Registro do Service Worker inserido.")
  else:
    print("OK: web/index.html já tem registro do Service Worker.")

  if changed:
    html_path.write_text(content, encoding="utf-8")


def ensure_sw_js(project_root: Path) -> None:
  sw_path = project_root / "web" / "sw.js"
  if not sw_path.exists():
    sw_path.write_text(DEFAULT_SW_JS, encoding="utf-8")
    print("OK: Criei web/sw.js.")
  else:
    print("OK: web/sw.js já existe.")


def ensure_line_after(text: str, anchor_regex: str, line_to_add: str) -> str:
  if line_to_add in text:
    return text
  m = re.search(anchor_regex, text, flags=re.MULTILINE)
  if not m:
    return line_to_add + "\n" + text
  insert_at = m.end()
  return text[:insert_at] + "\n" + line_to_add + "\n" + text[insert_at:]


def patch_api_server(project_root: Path) -> None:
  api_path = project_root / "src" / "api_server.py"
  if not api_path.exists():
    print("ERRO: Não achei src/api_server.py")
    sys.exit(1)

  text = api_path.read_text(encoding="utf-8", errors="ignore")
  original = text

  # Garante StaticFiles import
  if "from fastapi.staticfiles import StaticFiles" not in text:
    text = ensure_line_after(
      text,
      r"^\s*from\s+fastapi\s+import\s+.*$",
      "from fastapi.staticfiles import StaticFiles"
    )

  # Garante FileResponse import (sem quebrar o import existente)
  if "FileResponse" not in text:
    if re.search(r"^\s*from\s+fastapi\.responses\s+import\s+.*$", text, flags=re.MULTILINE):
      # acrescenta ", FileResponse" nessa linha
      def _add_fileresponse(m):
        line = m.group(0)
        if "FileResponse" in line:
          return line
        return line.rstrip() + ", FileResponse"
      text = re.sub(r"^\s*from\s+fastapi\.responses\s+import\s+.*$", _add_fileresponse, text, count=1, flags=re.MULTILINE)
    else:
      text = ensure_line_after(
        text,
        r"^\s*from\s+fastapi\s+import\s+.*$",
        "from fastapi.responses import FileResponse"
      )

  # Garante mount /icons
  mount_line = 'app.mount("/icons", StaticFiles(directory="web/icons"), name="icons")'
  if mount_line not in text:
    m = re.search(r"^\s*app\s*=\s*FastAPI\([^\)]*\)\s*$", text, flags=re.MULTILINE)
    if m:
      insert_at = m.end()
      text = text[:insert_at] + "\n" + mount_line + "\n" + text[insert_at:]
    else:
      text = text + "\n\n" + mount_line + "\n"

  # Garante rota /sw.js
  if re.search(r'@app\.get\(\s*["\']\/sw\.js["\']\s*\)', text) is None:
    sw_route = """
@app.get("/sw.js")
def serve_sw():
    return FileResponse("web/sw.js", media_type="application/javascript")
"""
    idx = text.find(mount_line)
    if idx != -1:
      after = idx + len(mount_line)
      text = text[:after] + "\n" + sw_route + "\n" + text[after:]
    else:
      text = text + "\n" + sw_route + "\n"

  if text != original:
    backup_file(api_path)
    api_path.write_text(text, encoding="utf-8")
    print("OK: Atualizei src/api_server.py (/icons e /sw.js).")
  else:
    print("OK: src/api_server.py já parece OK.")


def main() -> None:
  project_root = Path(__file__).resolve().parent

  icons_dir = project_root / "web" / "icons"
  icons_dir.mkdir(parents=True, exist_ok=True)
  print(f"OK: Pasta pronta: {icons_dir}")

  patch_index_html(project_root)
  ensure_sw_js(project_root)
  patch_api_server(project_root)

  print("\nTestes:")
  print("  http://127.0.0.1:8000/icons/favicon-32.png")
  print("  http://127.0.0.1:8000/icons/site.webmanifest")
  print("  http://127.0.0.1:8000/sw.js")


if __name__ == "__main__":
  main()
