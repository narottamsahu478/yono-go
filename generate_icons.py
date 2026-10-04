import os
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow library missing. Installing it via pip...")
    import subprocess
    subprocess.check_call(["pip", "install", "pillow"])
    from PIL import Image, ImageDraw, ImageFont

def create_icon(size, filename):
    # Dark modern background theme matching your app (#090b10)
    image = Image.new("RGBA", (size, size), color="#090b10")
    draw = ImageDraw.Draw(image)
    
    # Draw a nice glowing border/accent frame
    margin = int(size * 0.08)
    draw.rounded_rectangle(
        [(margin, margin), (size - margin, size - margin)],
        radius=int(size * 0.2),
        outline="#0099ff",
        width=int(size * 0.03)
    )
    
    # Draw text "SE" (SPYEYE short text for icon)
    try:
        # Try loading default system font or fallback
        font_size = int(size * 0.42)
        font = ImageFont.load_default()
    except Exception:
        font = None

    text = "SE"
    # Get text bounding box for centering
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    position = ((size - text_width) / 2, (size - text_height) / 2 - (size * 0.05))
    draw.text(position, text, fill="#38bdf8", font=font)
    
    # Save into shared folder
    shared_dir = Path("shared")
    shared_dir.mkdir(exist_ok=True)
    file_path = shared_dir / filename
    image.save(file_path, "PNG")
    print(f"Successfully generated: {file_path}")

if __name__ == "__main__":
    print("Generating PWA App Icons for SPYEYE...")
    create_icon(192, "icon-192.png")
    create_icon(512, "icon-512.png")
    print("All icons created successfully inside the 'shared/' folder!")

