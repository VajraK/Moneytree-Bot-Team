import os
import time
import requests
import re
import logging
from logging.handlers import TimedRotatingFileHandler
import yaml
from web3 import Web3
from bs4 import BeautifulSoup
from retry import retry
import threading
from pieces.market_cap_calculator import calculate_market_cap, format_market_cap

# Get the absolute path of the parent directory
parent_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Define log directory and ensure it exists
log_directory = os.path.join(parent_directory, 'logs/mtb')
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

# Set up a TimedRotatingFileHandler to archive logs every day
log_path = os.path.join(log_directory, 'mtb.log')

# Configure the logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Create a TimedRotatingFileHandler that rotates the log file daily
file_handler = TimedRotatingFileHandler(log_path, when='midnight', interval=1, backupCount=30, encoding='utf-8')
file_handler.suffix = "%Y%m%d"  # Suffix to add the date to the archived logs (e.g., 'mtdb-20231201.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# Construct the config file path in the parent directory
config_file_path = os.path.join(parent_directory, 'config.yaml')

try:
    with open(config_file_path, 'r') as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    logging.error(f"Configuration file '{config_file_path}' not found.")
    exit()
except yaml.YAMLError as exc:
    logging.error(f"Error parsing YAML file: {exc}")
    exit()

# Access configuration values
ETEREUM_NODE_URL = config['ETEREUM_NODE_URL']
TELEGRAM_BOT_TOKEN = config['MTB_TELEGRAM_BOT_TOKEN']
CHAT_ID = config['MTB_CHAT_ID']
ADDRESS_MAP = {addr.lower(): name for addr, name in config['ADDRESSES_TO_MONITOR'].items()}
ADDRESSES_TO_MONITOR = list(ADDRESS_MAP.keys())
ADDRESS_NAMES = list(ADDRESS_MAP.values())
TRADING_BOT_URL = 'http://localhost:5000/transaction'

SEND_TELEGRAM_MESSAGES = config['SEND_TELEGRAM_MESSAGES']
ALLOW_SWAP_MESSAGES_ONLY = config['ALLOW_SWAP_MESSAGES_ONLY']
ALLOW_AGGREGATED_MESSAGES_ALSO = config['ALLOW_AGGREGATED_MESSAGES_ALSO']
ALLOW_MTDB_INTERACTION = config['ALLOW_MTDB_INTERACTION']

# Bypassing proxies in local environment
proxies = {
    "http": None,
    "https": None,
}

# Ensure required environment variables are set
if not ADDRESSES_TO_MONITOR or not ADDRESS_NAMES:
    logging.error("ADDRESSES_TO_MONITOR or ADDRESS_NAMES environment variable is not set")
    exit()

# Initialize web3 with Ethereum Node
web3 = Web3(Web3.HTTPProvider(ETEREUM_NODE_URL))

if not web3.is_connected():
    logging.error("Failed to connect to Ethereum Node")
    exit()

logging.info(f"Connected to Ethereum Node. Monitoring transactions for addresses: {ADDRESS_MAP}")

def send_telegram_message(message):
    """
    Sends a message to the configured Telegram chat.
    """
    if not SEND_TELEGRAM_MESSAGES:
        logging.info("Sending Telegram messages is disabled.")
        logging.info(f"Message that would be sent: {message}")
        return
    
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    data = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'MarkdownV2',
        'disable_web_page_preview': True
    }
    response = requests.post(url, data=data)
    logging.info(f"Telegram response: {response.json()}")
    return response.json()

def clean_html(raw_html):
    """
    Removes HTML tags and extra spaces from a raw HTML string.
    """
    clean_text = re.sub('<.*?>', ' ', raw_html)
    clean_text = re.sub('\s+', ' ', clean_text).strip()
    clean_text = clean_text.replace('(', '〈').replace(')', '〉')
    
    # Remove unwanted strings
    unwanted_strings = ['Click to show more', 'Click to show less']
    for unwanted in unwanted_strings:
        clean_text = clean_text.replace(unwanted, '')

    print(f"Extracted token text: {clean_text}")
    return clean_text

def extract_token_link(action_line):
    """
    Extracts the token link, its text, and the token address from the action line if present.
    """
    token_link = None
    token_text = None
    token_address = None
    if '/token/' in action_line:
        match = re.search(r'/token/0x[0-9a-fA-F]{40}', action_line)
        if match:
            token_link = f"https://etherscan.io{match.group()}"
            token_address = match.group().split('/token/')[1]
            start_idx = action_line.find('>', match.end()) + 1
            end_idx = action_line.find('</a>', start_idx)
            token_text = action_line[start_idx:end_idx].strip()
            
            if token_text == 'ETH':
                token_text = 'ETH〈token〉'
                action_line = action_line[:start_idx] + token_text + action_line[end_idx:]

    return token_link, token_text, token_address, action_line


def escape_markdown(text):
    """
    Escapes Markdown special characters in the given text.
    """
    escape_chars = r'\_*~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def insert_zero_width_space(text):
    """
    Inserts a zero-width space between each digit in sequences of 9 to 30 digits
    followed by a dot or preceded by a dot.
    """
    zero_width_space = '\u200B'
    
    # Pattern for 9 to 30 digits followed by a dot
    pattern_following_dot = r'(\d{9,30})(\.)'
    # Pattern for 9 to 30 digits preceded by a dot
    pattern_preceding_dot = r'(\.)(\d{9,30})'
    
    def insert_spaces_following_dot(match):
        return zero_width_space.join(match.group(1)) + match.group(2)
    
    def insert_spaces_preceding_dot(match):
        return match.group(1) + zero_width_space.join(match.group(2))
    
    # Apply substitutions
    text = re.sub(pattern_following_dot, insert_spaces_following_dot, text)
    text = re.sub(pattern_preceding_dot, insert_spaces_preceding_dot, text)
    
    return text

@retry(tries=5, delay=2, backoff=2, jitter=(1, 3))
def get_transaction_action(tx_hash):
    """
    Fetches the transaction action from Etherscan and returns a cleaned version of it.
    """
    etherscan_url = f'https://etherscan.io/tx/{tx_hash}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    
    response = requests.get(etherscan_url, headers=headers)
    if response.status_code == 200:
        logging.info("Successfully fetched the Etherscan page.")
        soup = BeautifulSoup(response.text, 'html.parser')
        with open("etherscan_page.html", "w", encoding="utf-8") as file:
            file.write(response.text)
        
        lines = response.text.split('\n')
        for i, line in enumerate(lines):
            if 'Transaction Action: ' in line:
                logging.info(f"Found 'Transaction Action: ' line: {line.strip()}")
                
                # Check if the line contains other non-HTML text
                clean_line = clean_html(line.strip().replace('Transaction Action: ', '').strip())
                if clean_line:
                    action_line = line.strip().replace('Transaction Action: ', '').strip()
                elif clean_html(lines[i + 1].strip()):
                    # Use the following line if it contains non-HTML text
                    action_line = lines[i + 1].strip()
                else:
                    # Look for the next occurrence of 'Sponsored:'
                    sponsored_index = next((j for j in range(i, len(lines)) if 'Sponsored:' in lines[j]), None)
                    if sponsored_index:
                        action_line = '\n'.join(lines[i+1:sponsored_index]).strip()
                    else:
                        action_line = "No ACTION info available"
                
                # Extract token link and text and clean the action line
                token_link, token_text, token_adress, action_line = extract_token_link(action_line)
                cleaned_action = clean_html(action_line)
                if token_link and token_text:
                    cleaned_action = cleaned_action.replace(token_text, f"[{token_text}]({token_link})")
                
                # Insert zero-width space after the fifth digit following a dot in sequences of exactly nine digits
                cleaned_action = insert_zero_width_space(cleaned_action)

                # Escape markdown special characters
                cleaned_action = escape_markdown(cleaned_action)
                print(cleaned_action)
                
                return cleaned_action
        
        logging.info("Could not find 'Transaction Action:' section in the HTML.")
    else:
        logging.error(f"Failed to fetch the Etherscan page. Status code: {response.status_code}")
        response.raise_for_status()  # Raise an HTTPError if the status code is 4xx, 5xx
    return "No ACTION info available"


@retry(tries=5, delay=2, backoff=2, jitter=(1, 3))
def get_block_number():
    """
    Retrieves the latest block number from the Ethereum blockchain.
    """
    return web3.eth.block_number

def handle_event(tx):
    """
    Handles an event and sends a Telegram message if the transaction involves a monitored address.
    """
    from_address = tx['from'].lower()
    to_address = tx['to'].lower() if tx['to'] else None
    value = web3.from_wei(tx['value'], 'ether')
    tx_hash = tx['hash'].hex()

    from_name = ADDRESS_MAP.get(from_address, from_address)
    to_name = ADDRESS_MAP.get(to_address, to_address)

    from_name_link = f"[{from_name}](https://etherscan.io/address/{from_address})"
    to_name_link = f"[{to_name}](https://etherscan.io/address/{to_address})"
    tx_hash_link = f"[{tx_hash}](https://etherscan.io/tx/{tx_hash})"

    if from_address in ADDRESSES_TO_MONITOR:
        time.sleep(5)
        action_text = get_transaction_action(tx_hash)
        
        # Extract token link, text, and address
        token_link, token_text, token_address, action_text = extract_token_link(action_text)
        
        if ALLOW_SWAP_MESSAGES_ONLY and not (action_text.startswith("Swap") or (ALLOW_AGGREGATED_MESSAGES_ALSO and action_text.startswith("Aggregated"))):
            return  # Skip non-swap and non-aggregated transactions if only swaps are allowed

        # Calculate the Market Cap and include it in the message
        if token_address:
            market_cap_usd = calculate_market_cap(token_address)
            
            if market_cap_usd:
                # Convert the market cap to an integer and format it
                market_cap_formatted = format_market_cap(market_cap_usd)
                market_cap_formatted = market_cap_formatted.replace('.', '․')
                market_cap_text = f"${market_cap_formatted}"
            else:
                market_cap_text = "N/A"
        else:
            market_cap_text = "N/A" 

        transaction_details = {
            'from_name': from_name,
            'tx_hash': tx_hash,
            'action_text': action_text,
            'token_link': token_link,
            'token_text': token_text
        }
        if ALLOW_MTDB_INTERACTION:
            threading.Thread(target=notify_trading_bot, args=(transaction_details,)).start()

        token_action = ''
        if 'ETH For' in action_text or re.search(r'ETH \〈[^\)]+\〉 for', action_text):
            token_action += '⭐ *Token BUY* ⭐\n\n'
        if 'ETH On' in action_text or re.search(r'ETH \〈[^\)]+\〉 On', action_text):
            token_action += '💵 *Token SELL* 💵\n\n'

        message = (
            f'{token_action}'
            f'*Wallet:*\n{from_name_link}\n\n'
            f'*Transaction Hash:*\n{tx_hash_link}\n\n'
            f'*Action:*\n{action_text}\n\n'
            f'*Market Cap:*\n{market_cap_text}'
        )
        send_telegram_message(message)

    if to_address in ADDRESSES_TO_MONITOR:
        time.sleep(5)
        if ALLOW_SWAP_MESSAGES_ONLY:
            return  # Skip incoming messages if only swaps are allowed
        message = (
            f'⭐ *{to_name_link}: INCOMING* 💵\n\n'
            f'*From:*\n{from_address}\n\n'
            f'*To:*\n{to_address}\n\n'
            f'*Transaction Hash:*\n{tx_hash_link}'
        )
        send_telegram_message(message)

def notify_trading_bot(transaction_details):
    """
    Sends the transaction details to the trading bot via HTTP POST request.
    """
    try:
        response = requests.post(TRADING_BOT_URL, json=transaction_details, proxies=proxies)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)
        logging.info(f"Trading bot response: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending transaction details to trading bot: {e}")

def log_loop(poll_interval):
    """
    Main loop that polls for new blocks and handles transactions in those blocks.
    """
    latest_block = get_block_number()
    logging.info(f"Starting to monitor from block {latest_block}")
    while True:
        logging.info("Checking for new events...")
        current_block = get_block_number()
        if current_block > latest_block:
            for block_num in range(latest_block + 1, current_block + 1):
                block = web3.eth.get_block(block_num, full_transactions=True)
                for tx in block.transactions:
                    handle_event(tx)
            latest_block = current_block
        time.sleep(poll_interval)

def test_transaction(tx_hash):
    """
    Tests a specific transaction by hash.
    """
    try:
        tx = web3.eth.get_transaction(tx_hash)
        handle_event(tx)
    except Exception as e:
        logging.error(f"Error fetching transaction: {e}")

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Wallet Tracing Bot")
    parser.add_argument('--test-tx', type=str, help='Test a specific transaction hash')
    args = parser.parse_args()

    if args.test_tx:
        test_transaction(args.test_tx)
    else:
        log_loop(10)
