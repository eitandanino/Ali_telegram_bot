import requests
from bs4 import BeautifulSoup
import re
import urllib.parse
import browser_cookie3
import asyncio
import os
import nest_asyncio
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

from dotenv import load_dotenv

from iop import IopClient, IopRequest
import aiohttp
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, MessageHandler, filters

nest_asyncio.apply()
load_dotenv()

ALIEXPRESS_APP_KEY = os.getenv("ALIEXPRESS_APP_KEY")
ALIEXPRESS_APP_SECRET = os.getenv("ALIEXPRESS_APP_SECRET")
ALIEXPRESS_URL = os.getenv("ALIEXPRESS_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)  # Replace with your API key
model = genai.GenerativeModel("gemini-2.0-flash")


client = IopClient(ALIEXPRESS_URL, ALIEXPRESS_APP_KEY, ALIEXPRESS_APP_SECRET)
HEBREW_TRIGGERS = ["תחפש לי", "תמצא לי", "תשלוף לי"]


async def get_aliexpress_product_data(search_text: str):
    # Use browser-cookie3 to get the cookies from your Chrome session
    cj = browser_cookie3.chrome(domain_name="aliexpress.com")

    url = f'https://he.aliexpress.com/wholesale?SearchText={urllib.parse.quote(search_text)}'

    # Update headers for the request
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "DNT": "1",  # Do Not Track
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive"
    }

    # Perform the request with the cookies from the browser session
    response = requests.get(url, headers=headers, cookies=cj)

    html_content = response.text

    soup = BeautifulSoup(html_content, 'html.parser')

    # Find the script tag that contains the itemList data
    script_tag = soup.find('script', string=lambda t: t and 'itemList' in t and 'content' in t)

    item_ids = []

    if script_tag:
        script_text = script_tag.string

        # Extract the pdp_cdi JSON string from the script (if available)
        pattern = r'"pdp_cdi":"([^"]+)"'
        matches = re.findall(pattern, script_text)

        if matches:
            for match in matches:
                # Decode the URL-encoded JSON string
                decoded_json = urllib.parse.unquote(match)

                # Extract all itemId values from the decoded JSON string
                item_ids.extend(re.findall(r'"itemId":"(\d+)"', decoded_json))

        else:
            print("pdp_cdi data not found.")

        # Now, extract image URLs, titles, and prices using regex pattern
        pattern = re.compile(
            r'"image"\s*:\s*\{[^}]*?"imgUrl"\s*:\s*"([^"]+)"[^}]*\}.*?'
            r'"title"\s*:\s*\{[^}]*?"displayTitle"\s*:\s*"([^"]+)"[^}]*\}.*?'
            r'"salePrice"\s*:\s*\{[^}]*?"minPrice"\s*:\s*([\d.]+)[^}]*\}.*?',
            re.DOTALL
        )

        matches = pattern.findall(script_text)
        results = []

        for i, (img_url, title, price) in enumerate(matches, start=1):
            product_data = {}
            if i - 1 < len(item_ids):  # Ensure we are within bounds of item_ids
                full_img_url = f"https:{img_url}" if img_url.startswith("//") else img_url

                # Extract product ID (itemId) and construct the product URL
                product_url = f"https://www.aliexpress.com/item/{item_ids[i - 1]}.html"  # Use item_ids[i-1] to match the current product

                # Print the information
                # print(f"📦 Product #{i}")
                # print(f"🖼️ Image URL: {full_img_url}")
                # print(f"🏷️ Title: {title}")
                # print(f"💰 Sale Price: ₪ {price}")
                # print(f"🌐 Product URL: {product_url}")
                # print("-" * 40)
                product_data["link"] = product_url
                product_data['title'] = title
                product_data['image'] = full_img_url
                product_data['price'] = price

                results.append(product_data)
            else:
                print(f"Warning: No itemId available for product #{i}. Skipping...")
    else:
        print("No script tag with item list found.")
    return results[:4]


# === Title Enhancer ===
async def improve_title_with_gemini(title: str) -> str:
    prompt = (
        f"תשפר את שם המוצר הבא שיהיה מושך, ברור וקולח לקונים בעברית:\n\n"
        f"{title}\n\n"
        "החזר את השם המתוקן בלבד, בלי טקסט נוסף."
    )
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"⚠️ Error with Gemini: {e}")
        return title


# === AliExpress Promotion Link Generator ===
def generate_promotion_links(product_list):
    enriched_products = []

    for product in product_list:
        source_url = product['link']
        request = IopRequest('aliexpress.affiliate.link.generate')
        request.add_api_param('app_signature', ALIEXPRESS_APP_SECRET)
        request.add_api_param('promotion_link_type', '0')
        request.add_api_param('source_values', source_url)
        request.add_api_param('tracking_id', 'default')

        response = client.execute(request)

        try:
            promotion_links = (
                response.body
                .get('aliexpress_affiliate_link_generate_response', {})
                .get('resp_result', {})
                .get('result', {})
                .get('promotion_links', {})
                .get('promotion_link', [])
            )

            if promotion_links:
                product['link'] = promotion_links[0].get('promotion_link')
            else:
                product['link'] = source_url

        except AttributeError:
            product['link'] = source_url

        enriched_products.append(product)

    return enriched_products


# Updated fetch_and_create_collage function
async def fetch_and_create_collage(products, size=(500, 500)):
    processed_images = []

    for idx, product in enumerate(products, start=1):
        # Split the image URL to remove the .avif extension if present
        image_url = product["image"]

        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    continue
                img_bytes = await resp.read()

        image = Image.open(BytesIO(img_bytes)).convert("RGB")
        image = image.resize(size)

        draw = ImageDraw.Draw(image)
        font_size = 50
        font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"

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


# === Telegram Handler ===
async def handle_hebrew_search(update: Update, context):
    user_text = update.message.text.strip()

    if not any(user_text.startswith(trigger) for trigger in HEBREW_TRIGGERS):
        return

    query = None
    for trigger in HEBREW_TRIGGERS:
        if user_text.startswith(trigger):
            query = user_text.replace(trigger, "").strip()
            break

    if not query:
        await update.message.reply_text("❗ תכתוב מה לחפש אחרי 'תחפש לי', 'תמצא לי' או 'תשלוף לי'.")
        return

    # 👇 Send loading message and save reference to it
    loading_message = await update.message.reply_text(
        "🧙‍♂️הקוסם בודק מחירים, עובר על ביקורות ומכין לכם את הקסם🪄 — שנייה וזה אצלכם!!"
    )

    products = await get_aliexpress_product_data(query)

    # Filter out bundles
    products = [
        p for p in products
        if "BundleDeals" not in p["link"]
        and "bundle" not in p["link"].lower()
        and "productIds=" not in p["link"]
    ]

    products = generate_promotion_links(products)

    if not products:
        await update.message.reply_text("❌ לא נמצאו מוצרים רגילים (ללא באנדלים).")
        return

    collage_image = await fetch_and_create_collage(products)

    # Improve product titles and format message
    product_texts = []
    for i, product in enumerate(products, start=1):
        improved_title = await improve_title_with_gemini(product['title'])
        product_entry = (
            f"{i}. 🛍️ {improved_title}\n"
            f"💸 {product['price']} ש\"ח\n"
            f"🔗 {product['link']}"
        )
        product_texts.append(product_entry)

    final_message = "\n\n".join(product_texts)

    # 👇 Delete the loading message before sending the final one
    await loading_message.delete()

    await update.message.reply_photo(
        photo=collage_image,
        caption=final_message,
        parse_mode="HTML",
        reply_to_message_id=update.message.message_id
    )


async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_hebrew_search))
    print("🤖 Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
