from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo
import json, os

root = r"E:\Projects\HD2-ChatTranslator"
out = os.path.join(root, "assets")
os.makedirs(out, exist_ok=True)
brand = json.load(open(os.path.join(root, "branding.json"), encoding="utf-8"))
author = brand.get("author", "XD2233XD")
wid = brand.get("watermark_id", "")

S = 512
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
pts = [(80, 60), (432, 60), (432, 300), (256, 470), (80, 300)]
d.polygon(pts, fill=(18, 22, 25, 255), outline=(242, 163, 60, 255), width=18)
pts2 = [(110, 92), (402, 92), (402, 288), (256, 430), (110, 288)]
d.line(pts2 + [pts2[0]], fill=(90, 70, 30, 255), width=6)

font = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 145)
text = "HD2"
box = d.textbbox((0, 0), text, font=font)
d.text(((S - (box[2] - box[0])) / 2, 110 - box[1]), text, font=font, fill=(242, 163, 60, 255))

f2 = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 58)
t2 = "聊天翻译"
b2 = d.textbbox((0, 0), t2, font=f2)
d.text(((S - (b2[2] - b2[0])) / 2, 280), t2, font=f2, fill=(230, 230, 225, 255))

f3 = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 32)
t3 = "by " + author
b3 = d.textbbox((0, 0), t3, font=f3)
d.text(((S - (b3[2] - b3[0])) / 2, 365), t3, font=f3, fill=(150, 160, 166, 255))

meta = PngInfo()
meta.add_text("Author", author)
meta.add_text("Watermark-ID", wid)
meta.add_text("Software", "HD2 Chat Translator")
img.save(os.path.join(out, "icon.png"), pnginfo=meta)
img.save(os.path.join(out, "icon.ico"), sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print("ok", author, wid)
