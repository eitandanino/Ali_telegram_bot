def generate_promotion_links(product_list, client, app_secret, limit=4):
    """
    Generates affiliate promotion links for AliExpress products.
    
    Args:
        product_list (list): List of product dictionaries
        client: The IopClient instance to use for API calls
        app_secret (str): The AliExpress app secret
        limit (int, optional): Maximum number of products to process. Defaults to 4.
        
    Returns:
        list: List of products with promotion links
    """
    from iop import IopRequest
    
    enriched = []
    for product in product_list:
        source_url = product['link']
        request = IopRequest('aliexpress.affiliate.link.generate')
        request.add_api_param('app_signature', app_secret)
        request.add_api_param('promotion_link_type', '0')
        request.add_api_param('source_values', source_url)
        request.add_api_param('tracking_id', 'default')
        response = client.execute(request)

        try:
            promotion_links = (
                response.body.get('aliexpress_affiliate_link_generate_response', {})
                .get('resp_result', {})
                .get('result', {})
                .get('promotion_links', {})
                .get('promotion_link', [])
            )
            if promotion_links and promotion_links[0].get('promotion_link'):
                product['link'] = promotion_links[0].get('promotion_link')
                # ודא שכל השדות קיימים
                if all(k in product and product[k] for k in ['link', 'title', 'image', 'price']):
                    enriched.append(product)
            # עצור כשיש מספיק מוצרים
            if len(enriched) == limit:
                break
        except Exception:
            continue

    return enriched