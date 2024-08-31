import asyncio
from flask import Flask, request, jsonify
import os
from logging.handlers import TimedRotatingFileHandler
import json
import logging
import yaml
from web3 import Web3
from asgiref.wsgi import WsgiToAsgi
from datetime import datetime, timezone
from multiprocessing import Process
from pieces.filters import filter_message, extract_token_address, get_token_details
from pieces.uniswap import get_uniswap_v2_price, get_uniswap_v3_price
from pieces.text_utils import insert_zero_width_space
from pieces.telegram_utils import send_telegram_message
from pieces.market_cap import calculate_market_cap
from pieces.price_change_checker import check_no_change_threshold
from pieces.trading_buy import buy_token
from pieces.trading_sell import sell_token
from pieces.statistics import log_transaction

app = Flask(__name__)

# Get the absolute path of the parent directory
parent_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Define log directory and ensure it exists
log_directory = os.path.join(parent_directory, 'logs/mtdb')
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

# Set up a TimedRotatingFileHandler to archive logs every day
log_path = os.path.join(log_directory, 'mtdb.log')

# Configure the logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Create a TimedRotatingFileHandler that rotates the log file daily
file_handler = TimedRotatingFileHandler(log_path, when='midnight', interval=1, backupCount=30, encoding='utf-8')
file_handler.suffix = "%Y%m%d"  # Suffix to add the date to the archived logs (e.g., 'mtdb-20231201.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

logger.info("*** Started! Moneytree Trading Bot (MTdB) is now running. ***")

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

# Extract configuration values
ETEREUM_NODE_URL = config['ETEREUM_NODE_URL']
WETH_ADDRESS = config['WETH_ADDRESS']
UNISWAP_V2_FACTORY_ADDRESS = config['UNISWAP_V2_FACTORY_ADDRESS']
UNISWAP_V3_FACTORY_ADDRESS = config['UNISWAP_V3_FACTORY_ADDRESS']
AMOUNT_OF_ETH = config['AMOUNT_OF_ETH']
PRICE_INCREASE_THRESHOLD = config['PRICE_INCREASE_THRESHOLD']
PRICE_DECREASE_THRESHOLD = config['PRICE_DECREASE_THRESHOLD']
NO_CHANGE_THRESHOLD = config['NO_CHANGE_THRESHOLD']
NO_CHANGE_TIME_MINUTES = config['NO_CHANGE_TIME_MINUTES']
TELEGRAM_BOT_TOKEN = config['MTdB_TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID = config['MTdB_CHAT_ID']
MOONBAG = config['MOONBAG']
MIN_MARKET_CAP = config['MIN_MARKET_CAP']
MAX_MARKET_CAP = config['MAX_MARKET_CAP']

# Feature toggles
SEND_TELEGRAM_MESSAGES = config['SEND_TELEGRAM_MESSAGES']
ALLOW_MULTIPLE_TRANSACTIONS = config['ALLOW_MULTIPLE_TRANSACTIONS']
ENABLE_MARKET_CAP_FILTER = config['ENABLE_MARKET_CAP_FILTER']
ENABLE_PRICE_CHANGE_CHECKER = config['ENABLE_PRICE_CHANGE_CHECKER']
ENABLE_TRADING = config['ENABLE_TRADING']

# Load addresses to monitor from the configuration
ADDRESSES_TO_MONITOR = config['ADDRESSES_TO_MONITOR']

# Create a dictionary for address-to-name mapping
ADDRESS_MAP = {addr.lower(): name for addr, name in ADDRESSES_TO_MONITOR.items()}

# Initialize web3
web3 = Web3(Web3.HTTPProvider(ETEREUM_NODE_URL))

# Load the Uniswap V2 and V3 ABIs
with open('abis/IUniswapV2Factory.json') as file:
    uniswap_v2_factory_abi = json.load(file)["abi"]

with open('abis/IUniswapV2Pair.json') as file:
    uniswap_v2_pair_abi = json.load(file)["abi"]

with open('abis/IUniswapV2ERC20.json') as file:
    uniswap_v2_erc20_abi = json.load(file)["abi"]

with open('abis/IUniswapV3Factory.json') as file:
    uniswap_v3_factory_abi = json.load(file)

with open('abis/IUniswapV3Pool.json') as file:
    uniswap_v3_pool_abi = json.load(file)

# Create factory contract instances
uniswap_v2_factory = web3.eth.contract(address=Web3.to_checksum_address(UNISWAP_V2_FACTORY_ADDRESS), abi=uniswap_v2_factory_abi)
uniswap_v3_factory = web3.eth.contract(address=Web3.to_checksum_address(UNISWAP_V3_FACTORY_ADDRESS), abi=uniswap_v3_factory_abi)

def calculate_token_amount(eth_amount, token_price):
    return eth_amount / token_price

def get_token_decimals(token_address):
    token_address = Web3.to_checksum_address(token_address)
    token_contract = web3.eth.contract(address=token_address, abi=uniswap_v2_erc20_abi)
    decimals = token_contract.functions.decimals().call()
    logging.info(f"Token decimals for {token_address}: {decimals}")
    return decimals

def format_large_number(number):
    if number >= 1_000_000_000:
        return f"{number / 1_000_000_000:.1f}B"
    elif number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    elif number >= 1_000:
        return f"{number / 1_000:.1f}K"
    else:
        return str(number)

async def monitor_price(token_address, initial_price, token_decimals, transaction_details):
    from_name = transaction_details['from_name']
    tx_hash = transaction_details['tx_hash']
    symbol = transaction_details['symbol']
    token_amount = transaction_details['token_amount']
    initial_eth_balance = transaction_details['initial_eth_balance']
    from_address = ADDRESS_MAP.get(from_name.lower())

    monitoring_id = tx_hash[:8]

    start_time = datetime.now(timezone.utc)
    sell_reason = ''
    price_history = []
    use_moonbag = False  # Initialize use_moonbag to ensure it is always defined

    logging.info(f"Started monitoring for transaction {monitoring_id}. Initial price: {initial_price}, Token: {symbol}")

    while True:
        try:
            current_price = None
            # Try fetching from Uniswap V2 first
            v2_price, _ = get_uniswap_v2_price(web3, uniswap_v2_factory, token_address, WETH_ADDRESS, token_decimals, uniswap_v2_pair_abi)
            
            if v2_price is not None and v2_price > 0:
                current_price = v2_price
                current_price = current_price * (10 ** token_decimals)
            else:
                # Fallback to Uniswap V3 if V2 fails
                v3_price, _ = get_uniswap_v3_price(web3, uniswap_v3_factory, token_address, WETH_ADDRESS, token_decimals, uniswap_v3_pool_abi)
                if v3_price is not None and v3_price > 0:
                    current_price = v3_price
                    current_price = current_price * (10 ** token_decimals)

            # Skip this iteration if no valid price is fetched
            if current_price is None:
                logging.warning(f"Failed to fetch a valid price for token {symbol} on both Uniswap V2 and V3. Retrying...")
                await asyncio.sleep(3)
                continue  # Retry fetching the price after a delay

            # Only proceed with valid prices
            price_history.append((datetime.now(timezone.utc), current_price))

            price_increase = (current_price - initial_price) / initial_price
            price_decrease = (initial_price - current_price) / initial_price
            percent_change = ((current_price - initial_price) / initial_price) * 100

            # Log the valid price
            logging.info(f"Monitoring {monitoring_id} — Current price: {current_price} ETH ({percent_change:.2f}%). — {token_amount} {symbol}.")

            # Sell conditions...
            if price_increase >= PRICE_INCREASE_THRESHOLD:
                sell_reason = f"Price increased by {price_increase * 100:.2f}%"
                use_moonbag = True
                break
            elif price_decrease >= PRICE_DECREASE_THRESHOLD:
                sell_reason = f"Price decreased by {price_decrease * 100:.2f}%"
                use_moonbag = False
                break

            if ENABLE_PRICE_CHANGE_CHECKER:
                no_change, token_amount_to_sell, sell_reason, start_time = check_no_change_threshold(
                    start_time, price_history, monitoring_id, symbol, token_amount)
                if no_change:
                    use_moonbag = False
                    break

            await asyncio.sleep(2)

        except Exception as e:
            logging.error(f"Error during monitoring for token {symbol}: {e}")
            break

    # Execute this block after the loop ends
    sell_tx_hash = None
    profit_or_loss = None
    try:
        if ENABLE_TRADING:
            token_decimals = get_token_decimals(token_address)
            token_amount = token_amount * (10 ** token_decimals)
            sell_tx_hash, profit_or_loss = sell_token(token_address, token_amount, initial_eth_balance, tx_hash, use_moonbag)  # Pass initial_eth_balance here
            logging.info(f"Monitoring {monitoring_id} — Sell transaction sent with hash: {sell_tx_hash}")
    except Exception as e:
        logging.error(f"Error during sell: {e}")
        
    if sell_tx_hash is None:
        sell_tx_hash = "Transaction failed"
    
    if profit_or_loss is None or isinstance(profit_or_loss, str):

        profit_or_loss_display = "Could not calculate"
    else:
        profit_or_loss_display = f"🏆 {profit_or_loss:.18f} ETH" if profit_or_loss > 0 else f"{profit_or_loss:.18f} ETH"

    messageS = (
        f'🟢 *SELL!* 🟢\n\n'
        f'*From:*\n[{from_name}](https://etherscan.io/address/{from_address})\n\n'
        f'*Original Transaction Hash:*\n[{tx_hash}](https://etherscan.io/tx/{tx_hash})\n\n'
        f'*Sell Transaction Hash:*\n[{sell_tx_hash}](https://etherscan.io/tx/{sell_tx_hash})\n\n'
        f'*Reason:*\n{sell_reason}\n\n'
        f'*Profit/Loss:*\n{profit_or_loss_display}.\n\n'
    )
    if use_moonbag:
        messageS += f'*Moonbag:*\n{token_amount * MOONBAG} {symbol}'
    send_telegram_message(insert_zero_width_space(messageS))

    logging.info(f"Monitoring {monitoring_id} — Monitoring ended due to sell conditions.")

def handle_transaction(data):
    # Reconfigure logging in the child process to include the PID
    logger = logging.getLogger()  # Get the root logger
    for handler in logger.handlers[:]:  # Remove all old handlers
        logger.removeHandler(handler)
    
    # Reconfigure the logging to include the PID
    file_handler = TimedRotatingFileHandler(log_path, when='midnight', interval=1, backupCount=30, encoding='utf-8')
    file_handler.suffix = "%Y%m%d"
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(process)d - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)

    logger.info(f"Starting a new process to handle the transaction. PID: {os.getpid()}")
    
    # The logic from your transaction handler
    initial_eth_balance = None

    if filter_message(data, ADDRESS_MAP.values()):
        logger.info("Yes, it passes the filters")
        action_text_cleaned = data.get('action_text').replace('\\', '')
        token_address = extract_token_address(action_text_cleaned)
        if token_address:
            logger.info(f"Extracted token address: {token_address}")

            name, symbol, decimals = get_token_details(web3, token_address, uniswap_v2_erc20_abi)
            logger.info(f"Token name: {name}")
            logger.info(f"Token symbol: {symbol}")

            # Statistics
            log_transaction({
                "time": datetime.now(timezone.utc).isoformat(),  # Current UTC time
                "post_hash": data.get("tx_hash"),  # Using 'tx_hash' for post hash
                "wallet_name": data.get("from_name"),  # Using 'from_name' for wallet name
                "token_symbol": symbol,  # Token symbol
                "token_hash": token_address,
                "amount_of_eth": AMOUNT_OF_ETH,  # Amount of ETH
                "buy": "",
                "buy_tx": "",
                "sell": "",  # Initial status when transaction is received
                "sell_tx": "",
                "fail": "",  # No fail reason yet
                "profit_loss": ""  # Profit/loss not calculated yet
            })

            if ENABLE_MARKET_CAP_FILTER:
                # Check market cap
                market_cap_usd = calculate_market_cap(token_address)
                if market_cap_usd is None:
                    logger.info("Market cap not available. Skipping the buy.")
                    log_transaction({
                        "post_hash": data.get("tx_hash"),
                        "buy": "NO",
                        "sell": "NO",
                        "fail": "Market cap not available.",
                        "profit_loss": ""
                    })
                    return
                
                if market_cap_usd < MIN_MARKET_CAP or market_cap_usd > MAX_MARKET_CAP:
                    logger.info(f"Market cap {market_cap_usd} USD not within the specified range. Skipping the buy.")
                    log_transaction({
                        "post_hash": data.get("tx_hash"),
                        "buy": "NO",
                        "sell": "NO",
                        "fail": "Market cap not within the specified range.",
                        "profit_loss": ""
                    })
                    return

            initial_price, pair_address = get_uniswap_v2_price(web3, uniswap_v2_factory, token_address, WETH_ADDRESS, decimals, uniswap_v2_pair_abi)
            if initial_price is None:
                initial_price, pair_address = get_uniswap_v3_price(web3, uniswap_v3_factory, token_address, WETH_ADDRESS, decimals, uniswap_v3_pool_abi)
            
            if initial_price is not None:
                logger.info(f"Pair/Pool address: {pair_address}")
                logger.info(f"Token price: {initial_price} ETH")
                token_amount = calculate_token_amount(AMOUNT_OF_ETH, initial_price)
                logger.info(f"Approximately {token_amount} {symbol} would be purchased for {AMOUNT_OF_ETH} ETH.")

                # Send Telegram message for buy
                from_name = data.get('from_name')
                tx_hash = data.get('tx_hash')
                from_address = ADDRESS_MAP.get(from_name.lower())
                tx_hash_link = f"[{tx_hash}](https://etherscan.io/tx/{tx_hash})"
                from_name_link = f"[{from_name}](https://etherscan.io/address/{from_address})"

                # Add "✧[test]✧" to the top of the message if trading is disabled
                messageB = "\n✧[test]✧\n\n" if not ENABLE_TRADING else ""
                
                messageB += (
                    f'🟡 *BUY!* 🟡\n\n'
                    f'*From:*\n{from_name_link}\n\n'
                    f'*Copied Transaction Hash:*\n{tx_hash_link}\n\n'
                )
                if ENABLE_MARKET_CAP_FILTER:
                    messageB += f'*Market Cap:*\n{format_large_number(market_cap_usd)} USD\n\n'

                # If trading is enabled, execute the buy transaction
                if ENABLE_TRADING:
                    # Capture token amount, transaction hash, initial ETH balance, and initial price from buy_token function
                    token_amount, buy_tx_hash, initial_eth_balance, initial_price = buy_token(token_address, AMOUNT_OF_ETH, tx_hash)

                    if token_amount is None:
                        logger.error(f"No token amount for token {token_address}.")
                        return

                    # Fetch token decimals
                    token_decimals = get_token_decimals(token_address)
                    if token_decimals is None:
                        logger.error(f"Failed to fetch decimals for token {token_address}.")
                        log_transaction({
                            "post_hash": tx_hash,
                            "sell": "NO",
                            "fail": "Failed to fetch token decimals.",
                            "profit_loss": ""
                        })
                        return
                    else:
                        token_amount = token_amount / (10 ** token_decimals)
                        initial_price = initial_price / (10 ** token_decimals)
                    
                    # Check if the buy transaction was successful
                    if buy_tx_hash is None or token_amount is None:
                        # Log the reason for skipping further actions
                        if initial_eth_balance is not None and initial_eth_balance < web3.to_wei(AMOUNT_OF_ETH, 'ether'):
                            logger.warning(f"Insufficient ETH balance for the transaction. Current balance: {web3.from_wei(initial_eth_balance, 'ether')} ETH. Skipping the buy.")
                        else:
                            logger.warning(f"Buy transaction was skipped or failed for another reason.")
                        
                        return
                    
                    # If the buy was successful, log the details
                    logger.info(f"Buy transaction completed successfully. Transaction hash: {buy_tx_hash}, token amount: {token_amount}, "
                                f"initial ETH balance: {initial_eth_balance}, initial price: {initial_price}.")

                    messageB += f'*Buy Transaction Hash:*\n[{buy_tx_hash}](https://etherscan.io/tx/{buy_tx_hash})\n\n'  # Add the buy transaction hash

                messageB += (
                    f'*Action:*\nApproximately {token_amount} [{symbol}](https://etherscan.io/token/{token_address}) purchased for {AMOUNT_OF_ETH} ETH.\n'
                )

                send_telegram_message(insert_zero_width_space(messageB))

                # Prepare transaction details for monitoring
                transaction_details = {
                    'from_name': from_name,
                    'tx_hash': tx_hash,
                    'symbol': symbol,
                    'token_amount': token_amount,
                    'token_address': token_address,
                    'initial_price': initial_price,
                    'token_decimals': decimals,
                    'initial_eth_balance': initial_eth_balance
                }

                if ALLOW_MULTIPLE_TRANSACTIONS:
                    asyncio.run(monitor_price(token_address, initial_price, decimals, transaction_details))
                else:
                    asyncio.run(monitor_price(token_address, initial_price, decimals, transaction_details))
            else:
                logger.info("Token price not available on either Uniswap V2 or V3.")
        else:
            logger.info("Token address not found in the action text.")
    else:
        logger.info("No, it does not pass the filters")

@app.route('/transaction', methods=['POST'])
def transaction():
    data = request.json
    logger.info('—————————————————————————————————————————————————————————————————————————————————————————————————————————')
    logger.info(f"Received transaction data: {data}")

    # Start a new process to handle the transaction
    p = Process(target=handle_transaction, args=(data,))
    p.start()
    
    return jsonify({'status': 'processing'}), 200

def run_server():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    asgi_app = WsgiToAsgi(app)
    import uvicorn
    uvicorn.run(asgi_app, host='0.0.0.0', port=5000, timeout_keep_alive=0)
