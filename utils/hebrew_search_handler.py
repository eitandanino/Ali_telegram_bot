from telegram import Update
from io import BytesIO

async def handle_hebrew_search(update: Update, context, model, get_aliexpress_product_data, 
                              generate_promotion_links, fetch_and_create_collage, 
                              improve_title_with_gemini, translate_and_optimize_query,
                              client, app_secret, hebrew_triggers):
    """
    Handles Hebrew search requests for AliExpress products via Telegram.
    
    Args:
        update (Update): The Telegram update object
        context: The Telegram context object
        model: The Gemini model instance
        get_aliexpress_product_data: Function to get product data
        generate_promotion_links: Function to generate promotion links
        fetch_and_create_collage: Function to create image collage
        improve_title_with_gemini: Function to improve product titles
        translate_and_optimize_query: Function to translate and optimize queries
        client: The IopClient instance
        app_secret: The AliExpress app secret
        hebrew_triggers: List of Hebrew trigger phrases
        
    Returns:
        None
    """
    user_text = update.message.text.strip()
    if not any(user_text.startswith(trigger) for trigger in hebrew_triggers):
        await update.message.reply_text(
            "חברים על מנת לחפש תרשמו:\nתחפש לי / תמצא לי + תיאור המוצר"
        )
        return

    query = None
    for trigger in hebrew_triggers:
        if user_text.startswith(trigger):
            query = user_text.replace(trigger, "").strip()
            break

    if not query:
        await update.message.reply_text("❗ תכתוב מה לחפש אחרי 'תחפש לי', 'תמצא לי' או 'תשלוף לי'.")
        return

    loading_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🧙‍♂️הקוסם בודק מחירים, עובר על ביקורות ומכין לכם את הקסם🪄 — שנייה וזה אצלכם!!"
    )

    # Translate and optimize the query before searching
    optimized_query = await translate_and_optimize_query(query, model)
    print(optimized_query)
    products = await get_aliexpress_product_data(optimized_query)
    products = [
        p for p in products
        if "BundleDeals" not in p["link"]
           and "bundle" not in p["link"].lower()
           and "productIds=" not in p["link"]
    ]
    products = generate_promotion_links(products, client, app_secret)
    products = products[:4]

    if not products:
        await update.message.reply_text("מצטער לא נמצאו תוצאות... תנסה/י שוב הפעם בניסוח שונה.")
        return

    collage_image = await fetch_and_create_collage(products)
    product_texts = []

    for i, product in enumerate(products, start=1):
        improved_title = await improve_title_with_gemini(product['title'], model)
        product_entry = (
            f"{i}. 🛍️ {improved_title}\n"
            f"💸 {product['price']} ש\"ח\n"
            f"🔗 {product['link']}"
        )
        product_texts.append(product_entry)

    final_message = "\n\n".join(product_texts) + "\n\nהקוסם AI"

    await update.message.reply_photo(
        photo=collage_image,
        caption=final_message,
        parse_mode="HTML",
        reply_to_message_id=update.message.message_id
    )
    await loading_message.delete()