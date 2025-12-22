from PIL import Image, ImageDraw

W = H = 512
img = Image.new("RGBA", (W, H), (10, 18, 28, 255))
d = ImageDraw.Draw(img)

# base do "pé quadrado"
d.rounded_rectangle([140, 190, 380, 440], radius=28, fill=(20, 180, 120, 255))

# dedos
toes = [
    (150, 130, 200, 180),
    (210, 115, 260, 165),
    (270, 115, 320, 165),
    (330, 130, 380, 180),
]
for r in toes:
    d.rounded_rectangle(r, radius=16, fill=(20, 180, 120, 255))

# detalhe tipo pixel
for x in range(160, 370, 24):
    d.rectangle([x, 230, x+8, 238], fill=(0, 0, 0, 60))

img.save("logo.png")
print("OK: logo.png criado na raiz do projeto")
