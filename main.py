import json
import time
import requests
from bs4 import BeautifulSoup
import re
import urllib.parse
import asyncio
import os
import nest_asyncio

from dotenv import load_dotenv

from iop import IopClient
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, MessageHandler, filters

from utils.query_optimizer import translate_and_optimize_query
from utils.title_improver import improve_title_with_gemini
from utils.promotion_links import generate_promotion_links
from utils.hebrew_search_handler import handle_hebrew_search
from utils.image_collage import fetch_and_create_collage
from utils.webhook_manager import delete_webhook

# Apply necessary asynchronous handling
nest_asyncio.apply()

# Load environment variables from .env file
load_dotenv()

# Environment variables
ALIEXPRESS_APP_KEY = os.getenv("ALIEXPRESS_APP_KEY")
ALIEXPRESS_APP_SECRET = os.getenv("ALIEXPRESS_APP_SECRET")
ALIEXPRESS_URL = os.getenv("ALIEXPRESS_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# Set up the client for AliExpress API
client = IopClient(ALIEXPRESS_URL, ALIEXPRESS_APP_KEY, ALIEXPRESS_APP_SECRET)

# Triggers for Hebrew searches
HEBREW_TRIGGERS = ["תחפש לי", "תמצא לי", "תשלוף לי"]


def load_cookies_from_browser_export(path: str) -> dict:
    with open(path, "r") as f:
        raw_cookies = json.load(f)
    return {cookie["name"]: cookie["value"] for cookie in raw_cookies}


async def get_aliexpress_product_data(search_text: str):
    url = f'https://he.aliexpress.com/wholesale?SearchText={urllib.parse.quote(search_text)}'
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive"
    }
    cookies = load_cookies_from_browser_export("cookies.json")
    response = requests.get(url, headers=headers, cookies=cookies)
    html_content = response.text
    soup = BeautifulSoup(html_content, 'html.parser')

    script_tag = soup.find('script', string=lambda t: t and 'itemList' in t and 'content' in t)
    item_ids = []

    if script_tag:
        script_text = script_tag.string
        pattern = r'"pdp_cdi":"([^"]+)"'
        matches = re.findall(pattern, script_text)
        if matches:
            for match in matches:
                decoded_json = urllib.parse.unquote(match)
                item_ids.extend(re.findall(r'"itemId":"(\d+)"', decoded_json))

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
            if i - 1 < len(item_ids):
                full_img_url = f"https:{img_url}" if img_url.startswith("//") else img_url
                product_url = f"https://www.aliexpress.com/item/{item_ids[i - 1]}.html"
                product_data["link"] = product_url
                product_data['title'] = title
                product_data['image'] = full_img_url
                product_data['price'] = price
                results.append(product_data)
    return results


# Create a wrapper function to handle the Hebrew search
async def hebrew_search_handler(update: Update, context):
    await handle_hebrew_search(
        update=update,
        context=context,
        model=model,
        get_aliexpress_product_data=get_aliexpress_product_data,
        generate_promotion_links=generate_promotion_links,
        fetch_and_create_collage=fetch_and_create_collage,
        improve_title_with_gemini=improve_title_with_gemini,
        translate_and_optimize_query=translate_and_optimize_query,
        client=client,
        app_secret=ALIEXPRESS_APP_SECRET,
        hebrew_triggers=HEBREW_TRIGGERS
    )


async def main():
    application = Application.builder().token(BOT_TOKEN).build()
    message_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, hebrew_search_handler)
    application.add_handler(message_handler)
    await application.run_polling()


if __name__ == "__main__":
    delete_webhook(BOT_TOKEN)
    time.sleep(3)
    print("🤖 Bot is alive!")
    asyncio.get_event_loop().run_until_complete(main())
