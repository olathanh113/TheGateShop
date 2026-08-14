import os
from PIL import Image, ImageDraw

# Create a clean brand orange icon 180x180
def create_icon(size):
    img = Image.new('RGBA', (size, size), color=(234, 88, 12, 255))
    draw = ImageDraw.Draw(img)
    # Draw simple 'G' logo or stylized gate mark
    draw.rectangle([size * 0.2, size * 0.2, size * 0.8, size * 0.8], outline=(255, 255, 255, 255), width=max(2, int(size * 0.08)))
    return img

base_dir = r'c:\laragon\www\TheGateShop'

icon_180 = create_icon(180)
icon_180.save(os.path.join(base_dir, 'apple-touch-icon.png'), 'PNG')

icon_32 = create_icon(32)
icon_32.save(os.path.join(base_dir, 'favicon.png'), 'PNG')

icon_32.save(os.path.join(base_dir, 'favicon.ico'), format='ICO', sizes=[(16, 16), (32, 32), (48, 48)])

print('Generated favicon.ico, favicon.png, apple-touch-icon.png')
