"""Regenerate the macOS icon PNG with Pillow; the SVG is the editable vector reference."""
from pathlib import Path
from PIL import Image, ImageDraw

size = 1024
image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
gradient = Image.new("RGBA", (size, size))
pixels = gradient.load()
for y in range(size):
    for x in range(size):
        t = min(1.0, (x + y) / (2 * size))
        pixels[x, y] = (int(20 + 5 * t), int(27 + 97 * t), int(72 + 90 * t), 255)
mask = Image.new("L", (size, size), 0)
ImageDraw.Draw(mask).rounded_rectangle((32, 32, 991, 991), radius=220, fill=255)
image.paste(gradient, (0, 0), mask)
draw = ImageDraw.Draw(image)
# Add translucent film frame over a deep blue to teal macOS-style tile.
draw.rounded_rectangle((180, 248, 844, 774), radius=76, fill=(13, 25, 62, 240), outline=(166, 192, 255, 255), width=13)
draw.line((194, 352, 830, 352), fill=(116, 147, 220, 180), width=11)
draw.line((194, 670, 830, 670), fill=(116, 147, 220, 180), width=11)
for x in (226, 368, 510, 652):
    draw.rounded_rectangle((x, 279, x + 69, 322), radius=13, fill=(173, 199, 254, 216))
    draw.rounded_rectangle((x, 704, x + 69, 742), radius=12, fill=(173, 199, 254, 216))
draw.ellipse((375, 375, 649, 649), fill=(77, 97, 156, 255))
draw.polygon([(459, 417), (616, 506), (459, 604)], fill=(249, 251, 255, 255))
for x, top, bottom in ((274, 518, 556), (320, 489, 583), (366, 519, 558), (658, 523, 552), (704, 492, 584), (750, 523, 552)):
    draw.line((x, top, x, bottom), fill=(174, 239, 255, 255), width=20)
    draw.ellipse((x - 10, top - 10, x + 10, top + 10), fill=(174, 239, 255, 255))
    draw.ellipse((x - 10, bottom - 10, x + 10, bottom + 10), fill=(174, 239, 255, 255))
image.save(Path(__file__).with_name("AnimeDubberIcon.png"))
