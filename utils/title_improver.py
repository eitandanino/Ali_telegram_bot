async def improve_title_with_gemini(title: str, model) -> str:
    """
    Improves a product title to make it more attractive in Hebrew.
    
    Args:
        title (str): The original product title
        model: The Gemini model instance to use for title improvement
        
    Returns:
        str: The improved product title in Hebrew
    """
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