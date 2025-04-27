import re


async def translate_and_optimize_query(query: str, model) -> str:
    """
    Translates and optimizes a Hebrew product query for AliExpress search.
    
    Args:
        query (str): The original query in Hebrew
        model: The Gemini model instance to use for translation
        
    Returns:
        str: The optimized English query
    """
    prompt = (
        "You are an expert AliExpress search optimizer. "
        "Given a product description in Hebrew, translate it to English and expand it with relevant keywords and details so that AliExpress will understand exactly what the user is looking for. "
        "Return ONLY the improved English search query, without any explanations, brackets, or extra text. "
        "Do not include site names or anything except the search query itself.\n\n"
        f"{query}"
    )
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        # Remove anything in square brackets
        result = re.sub(r"\[.*?\]", "", result)
        # Remove trailing site names like '- AliExpress' or similar
        result = re.sub(r"-\s*AliExpress.*$", "", result, flags=re.IGNORECASE)
        # Remove extra spaces
        result = result.strip()
        return result
    except Exception as e:
        print(f"⚠️ Error with Gemini: {e}")
        return query