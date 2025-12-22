# src/tools/make_icons.py
# Gera favicons e app icons a partir de um PNG (recomendado: quadrado, >= 512x512)
# Uso:
#   py .\src\tools\make_icons.py --input .\assets\logo.png --out .\web\icons
#
# Saídas:
#   - favicon.ico (multi-size)
#   - favicon-16.png, favicon-32.png
#   - icon-180.png (apple)
#   - icon-192.png, icon-512.png (PWA)
#   - site.webmanifest

from __future__ import annotations
import argparse
import os
from pathlib import Path

def ensure_pillow():
    try:
        from PIL import Image  # noqa: F401
    except Exception:
        raise SystemExit(
            "Faltou a biblioteca Pillow.\n"
            "Instale assim:\n"
            "  py -m pip install pillow\n"
        )

def load_image(path: Path):
    from PIL import Image
    img = Image.open(path).convert("RGBA")
    return img

def fit_square(img):
    # recorta centralizado para quadrado (se a logo não for quadrada)
    w, h = img.size
    if w == h:
        return img
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))

def resize_png(img, size: int, out_path: Path):
    from PIL import Image
    out = img.resize((size, size), resample=Image.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path, format="PNG", optimize=True)

def save_favicon_ico(img, sizes: list[int], out_path: Path):
    from PIL import Image
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Pillow gera ICO com múltiplos tamanhos se você passar sizes=
    img_ico = img.resize((max(sizes), max(sizes)), resample=Image.LANCZOS)
    img_ico.save(out_path, format="ICO", sizes=[(s, s) for s in sizes])

def write_manifest(out_dir: Path):
    manifest = """{
  "name": "Square Foot",
  "short_name": "Square Foot",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0b1220",
  "theme_color": "#0b1220",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
"""
    (out_dir / "site.webmanifest").write_text(manifest, encoding="utf-8")

def main():
    ensure_pillow()

    p = argparse.ArgumentParser(description="Gera favicons e app icons a partir de um PNG.")
    p.add_argument("--input", "-i", required=True, help="Caminho do PNG de entrada (logo).")
    p.add_argument("--out", "-o", default="web/icons", help="Pasta de saída (default: web/icons).")
    args = p.parse_args()

    in_path = Path(args.input).resolve()
    out_dir = Path(args.out).resolve()

    if not in_path.exists():
        raise SystemExit(f"Arquivo de entrada não encontrado: {in_path}")

    img = load_image(in_path)
    img = fit_square(img)

    # Tamanhos padrão (bem compatíveis)
    resize_png(img, 16, out_dir / "favicon-16.png")
    resize_png(img, 32, out_dir / "favicon-32.png")
    resize_png(img, 180, out_dir / "icon-180.png")   # Apple touch icon
    resize_png(img, 192, out_dir / "icon-192.png")   # PWA
    resize_png(img, 512, out_dir / "icon-512.png")   # PWA

    save_favicon_ico(img, [16, 32, 48], out_dir / "favicon.ico")
    write_manifest(out_dir)

    print("OK! Ícones gerados em:", out_dir)
    for name in ["favicon.ico", "favicon-16.png", "favicon-32.png", "icon-180.png", "icon-192.png", "icon-512.png", "site.webmanifest"]:
        print(" -", out_dir / name)

if __name__ == "__main__":
    main()
