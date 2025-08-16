from PIL import Image
import os

# Path to the logo
logo_path = os.path.join('static', 'images', 'logo.png')
favicon_path = os.path.join('static', 'favicon.ico')

# Open the logo
img = Image.open(logo_path)

# Convert to RGBA if not already
if img.mode != 'RGBA':
    img = img.convert('RGBA')

# Create different sizes for the favicon
sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
favicon_images = []

for size in sizes:
    resized_img = img.resize(size, Image.Resampling.LANCZOS)
    favicon_images.append(resized_img)

# Save as .ico file with multiple sizes
favicon_images[0].save(
    favicon_path,
    format='ICO',
    sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
    append_images=favicon_images[1:]
)
