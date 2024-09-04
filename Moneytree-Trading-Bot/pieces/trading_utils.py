import logging
import os
import yaml
import json
import time
from web3 import Web3
from pieces.dexanalyzer_scraper import scrape_dexanalyzer

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

# Initialize web3
ETEREUM_NODE_URL = config['ETEREUM_NODE_URL']
web3 = Web3(Web3.HTTPProvider(ETEREUM_NODE_URL))

# Wallet details
WALLET_PRIVATE_KEY = config['WALLET_PRIVATE_KEY']
WALLET_ADDRESS = web3.eth.account.from_key(WALLET_PRIVATE_KEY).address

# Load priority fee
BASE_FEE_MULTIPLIER = config['BASE_FEE_MULTIPLIER']
PRIORITY_FEE_MULTIPLIER = config['PRIORITY_FEE_MULTIPLIER']
TOTAL_FEE_MULTIPLIER = config['TOTAL_FEE_MULTIPLIER']

# Slippage
SLIPPAGE_TOLERANCE = config['SLIPPAGE_TOLERANCE']

# Uniswap Router address
UNISWAP_V2_ROUTER_ADDRESS = Web3.to_checksum_address('0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D')  # Uniswap V2 Router
UNISWAP_V3_ROUTER_ADDRESS = Web3.to_checksum_address('0xE592427A0AEce92De3Edee1F18E0157C05861564')  # Uniswap V3 Router

# Load ABI files
with open('abis/IUniswapV2Factory.json') as file:
    uniswap_v2_factory_abi = json.load(file)["abi"]
with open('abis/IUniswapV3Factory.json') as file:
    uniswap_v3_factory_abi = json.load(file)
with open('abis/IUniswapV2Pair.json') as file:
    uniswap_v2_pair_abi = json.load(file)["abi"]
with open('abis/IUniswapV3Pool.json') as file:
    uniswap_v3_pool_abi = json.load(file)
with open('abis/IUniswapV2ERC20.json') as file:
    uniswap_v2_erc20_abi = json.load(file)["abi"]
with open('abis/IUniswapV2Router02.json') as file:
    uniswap_v2_router_abi = json.load(file)["abi"]
with open('abis/IUniswapV3Router.json') as file:
    uniswap_v3_router_abi = json.load(file)

# Create contract instances
uniswap_v2_router = web3.eth.contract(address=UNISWAP_V2_ROUTER_ADDRESS, abi=uniswap_v2_router_abi)
uniswap_v3_router = web3.eth.contract(address=UNISWAP_V3_ROUTER_ADDRESS, abi=uniswap_v3_router_abi)
uniswap_v2_factory = web3.eth.contract(address=Web3.to_checksum_address('0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f'), abi=uniswap_v2_factory_abi)
uniswap_v3_factory = web3.eth.contract(address=Web3.to_checksum_address('0x1F98431c8aD98523631AE4a59f267346ea31F984'), abi=uniswap_v3_factory_abi)

# Constants
WETH_ADDRESS = Web3.to_checksum_address('0xC02aaA39b223FE8D0A0E5C4F27eAD9083C756Cc2')

def retry_scam_check(token_address, retries=30, delay_seconds=10):
    for attempt in range(retries):
        # Get both the scam detection status and the scam reason from scrape_dexanalyzer
        scam_detected, scam_reason = scrape_dexanalyzer(token_address)
        
        if scam_detected:
            logging.warning(f"x SCAM detected for token {token_address}. Reason: {scam_reason}. Retrying ({attempt + 1}/{retries}) in {delay_seconds} seconds.")
            time.sleep(delay_seconds)
        else:
            logging.info(f"x No scam detected for token {token_address} on attempt {attempt + 1}. Proceeding with the buy.")
            return False, ""  # No scam detected, return False and no reason
    
    # If scam detected after all retries, return True and the final reason
    logging.warning(f"x SCAM detected for token {token_address} after {retries} retries. Skipping the buy. Final reason: {scam_reason}")
    return True, scam_reason  # Scam detected after all retries

def calculate_token_amount(eth_amount, token_price):
    logging.debug(f"Calculating token amount: ETH amount={eth_amount}, Token price={token_price}")
    return eth_amount / token_price

def check_token_balance(token_address):
    try:
        token_address = Web3.to_checksum_address(token_address)
        token_contract = web3.eth.contract(address=token_address, abi=uniswap_v2_erc20_abi)
        balance = token_contract.functions.balanceOf(WALLET_ADDRESS).call()
        return balance
    except Exception as e:
        logging.error(f"Error checking token balance: {e}")
        return None

def check_eth_balance():
    try:
        balance = web3.eth.get_balance(WALLET_ADDRESS)
        return balance
    except Exception as e:
        logging.error(f"Error checking ETH balance: {e}")
        return None

def wait_for_balance_change(initial_balance_func, token_address=None, expected_increase=True, max_attempts=90, delay_seconds=2):
    initial_balance = initial_balance_func(token_address) if token_address else initial_balance_func()
    for attempt in range(max_attempts):
        current_balance = initial_balance_func(token_address) if token_address else initial_balance_func()
        logging.info(f"Attempt {attempt + 1}: Current balance = {current_balance}; Initial banance = {initial_balance}")

        if expected_increase:
            if current_balance > initial_balance:
                return current_balance
        else:
            if current_balance < initial_balance:
                return current_balance

        logging.info(f"No balance change detected, waiting {delay_seconds} seconds before retrying...")
        time.sleep(delay_seconds)

    logging.error("No balance change detected after multiple attempts.")
    return None

def wait_for_approval(token_contract, token_address, amount_in_smallest_unit, max_attempts=90, delay_seconds=2):
    for attempt in range(max_attempts):
        allowance = token_contract.functions.allowance(WALLET_ADDRESS, UNISWAP_V2_ROUTER_ADDRESS).call()
        logging.info(f"Attempt {attempt + 1}: Current allowance = {allowance} tokens")
        if allowance >= amount_in_smallest_unit:
            return True
        logging.info(f"Allowance not sufficient yet, waiting {delay_seconds} seconds before retrying...")
        time.sleep(delay_seconds)
    logging.error("Allowance did not update after multiple attempts.")
    return False

def send_transaction(signed_txn):
    tx_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
    return tx_hash
