import requests

def delete_webhook(bot_token):
    """
    Deletes the Telegram webhook for the bot.
    
    Args:
        bot_token (str): The Telegram bot token
        
    Returns:
        None
    """
    url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
    try:
        response = requests.post(url)
        print(f"Webhook deleted: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Failed to delete webhook: {e}")