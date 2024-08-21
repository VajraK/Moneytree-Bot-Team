import requests
import re
import logging
import yaml
import os

# Get the absolute path of the parent directory
parent_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

# Construct the config file path in the parent directory
config_file_path = os.path.join(parent_directory, 'config.yaml')

try:
    with open(config_file_path, 'r') as file:
        config = yaml.safe_load(file)
except FileNotFoundError:
    logging.error(f"Configuration file '{config_file_path}' not found.")
    exit()
except yaml.YAMLError as exc:
    logging.error(f"Error parsing YAML file: {exc}")
    exit()

TELEGRAM_BOT_TOKEN = config['MTdB_TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID = config['MTdB_CHAT_ID']
SEND_TELEGRAM_MESSAGES = config['SEND_TELEGRAM_MESSAGES']

def send_telegram_message(message):
    """
    Sends a message to the configured Telegram chat.
    """
    if not SEND_TELEGRAM_MESSAGES:
        logging.info("Sending Telegram messages is disabled.")
        logging.info(f"Message that would be sent: {message}")
        return

    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    
    # Escape special characters for MarkdownV2
    escape_chars = r'\_~`>#+-=|{}.!'
    escaped_message = re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', message)

    data = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': escaped_message,
        'parse_mode': 'MarkdownV2',
        'disable_web_page_preview': True
    }

    logging.info(f"Sending Telegram message!")

    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        logging.info(f"Telegram response: {response.json()}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending message to Telegram: {e}")
        if response is not None:
            logging.error(f"Response content: {response.content}")
