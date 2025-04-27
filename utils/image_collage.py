import os
import re
import aiohttp
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

async def fetch_and_create_collage(products, size=(500, 500)):
    """
    Fetches product images and creates a collage with numbered indicators.
    
    Args:
        products (list): List of product dictionaries containing image URLs
        size (tuple, optional): Size of each image in the collage. Defaults to (500, 500).
        
    Returns:
        BytesIO: A BytesIO object containing the JPEG image data
    """
    processed_images = []
    for idx, product in enumerate(products, start=1):
        image_url = product["image"]

        # Clean up the image URL to end at the first valid image extension
        match = re.search(r"(https?://[^\s]+?\.(jpg|jpeg|png|webp|gif))", image_url, re.IGNORECASE)
        if match:
            image_url = match.group(1)

        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200 or "image" not in resp.headers.get("Content-Type", ""):
                    continue
                img_bytes = await resp.read()
        try:
            image = Image.open(BytesIO(img_bytes)).convert("RGB")
        except Exception as e:
            print(f"Failed to open image: {e} (URL: {image_url})")
            continue
        image = image.resize(size)

        draw = ImageDraw.Draw(image)
        font_size = 45
        font_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fonts', 'DejaVuSans.ttf')

        try:
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            font = ImageFont.load_default()

        text = str(idx)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        padding = 10
        box_width = text_width + padding
        box_height = text_height + padding
        box_x = (image.width - box_width) // 2
        box_y = size[1] // 10 - 20

        draw.rounded_rectangle(
            [box_x, box_y, box_x + box_width, box_y + box_height],
            radius=15,
            fill=(0, 200, 0)
        )

        text_x = box_x + (box_width - text_width) // 2
        text_y = box_y + (box_height - text_height) // 2 - 10

        draw.text((text_x, text_y), text, font=font, fill="white")
        processed_images.append(image)

    collage_width = size[0] * 2
    collage_height = size[1] * 2
    collage = Image.new("RGB", (collage_width, collage_height))

    for i, img in enumerate(processed_images):
        row = i // 2
        col = i % 2
        x = col * size[0]
        y = row * size[1]
        collage.paste(img, (x, y))

    output = BytesIO()
    collage.save(output, format="JPEG")
    output.seek(0)
    return output