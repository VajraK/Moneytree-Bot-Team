import logging
import os
import yaml
import json
import time
from datetime import datetime, timedelta, timezone
from web3 import Web3
from pieces.trading_utils import (
    retry_scam_check,
    check_eth_balance,
    check_token_balance,
    calculate_token_amount,
    wait_for_balance_change,
    send_transaction
)
from pieces.statistics import log_transaction
from pieces.uniswap import get_uniswap_v2_price, get_uniswap_v3_price

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

def buy_token(token_address, amount_eth, trans_hash, decimals):
    max_retries = 30  # Maximum number of retries
    retry_count = 0  # Track the number of retries

    # Retry delays: 3 seconds before 1st retry, 10 seconds before 2nd, 18 seconds before 3rd
    retry_delays = [5] * max_retries

    try:
        logging.info(f"Starting buy process for token: {token_address} with {amount_eth} ETH")

        # Ensure token_address is checksummed
        token_address = Web3.to_checksum_address(token_address)
        logging.debug(f"Checksummed token address: {token_address}")

        # Run DexAnalyzer Scraper with retry logic
        scam_detected, scam_reason = retry_scam_check(token_address)
        if scam_detected:
            # Log failure for scam detected
            log_transaction({
                "post_hash": trans_hash,
                "buy": "NO",
                "sell": "NO",
                "fail": scam_reason,
                "profit_loss": ""
            })
            return None, None, None, None

        # Check initial ETH balance before buy
        initial_eth_balance = check_eth_balance()
        if initial_eth_balance is None:
            raise Exception("Failed to check initial ETH balance.")
        logging.info(f"Initial ETH balance: {web3.from_wei(initial_eth_balance, 'ether')} ETH")


        # Check if the balance is sufficient
        required_balance = web3.to_wei(0.025 + amount_eth, 'ether')
        if initial_eth_balance < required_balance:
            logging.warning(f"Insufficient balance for transaction. Required: {web3.from_wei(required_balance, 'ether')} ETH")
            log_transaction({
                "post_hash": trans_hash,
                "buy": "NO",
                "sell": "NO",
                "fail": "Insufficient funds in wallet.",
                "profit_loss": ""
            })
            return None, None, initial_eth_balance, None

        # Check initial token balance
        initial_token_balance = check_token_balance(token_address)
        if initial_token_balance is None:
            raise Exception("Failed to check initial token balance.")
        logging.info(f"Initial token balance: {initial_token_balance}")

        # Determine transaction parameters
        deadline = int((datetime.now(timezone.utc) + timedelta(minutes=10)).timestamp())
        logging.debug(f"Transaction deadline: {deadline}, Slippage tolerance: {SLIPPAGE_TOLERANCE}")

        while retry_count < max_retries:
            try:
                # Get token price from Uniswap
                initial_price, pair_address = get_uniswap_v2_price(token_address, decimals)
                if initial_price is None:
                    initial_price, pair_address = get_uniswap_v3_price(token_address, decimals)
                if initial_price is None:
                    raise Exception("Token price not found on Uniswap V2 or V3.")
                logging.info(f"Token price: {initial_price}")

                # Calculate the estimated output amount
                estimated_output_amount = calculate_token_amount(web3.to_wei(amount_eth, 'ether'), initial_price)
                logging.info(f"Estimated output amount (without slippage): {estimated_output_amount}")

                # Calculate the minimum output amount (after applying slippage tolerance)
                amount_out_min = int(estimated_output_amount * (1 - SLIPPAGE_TOLERANCE))
                logging.info(f"Minimum output amount (amount_out_min) after slippage: {amount_out_min}")

                # Create the path for the swap (WETH -> Token)
                path = [WETH_ADDRESS, token_address]
                logging.debug(f"Swap path: {path}")

                # Create the transaction
                txn = uniswap_v2_router.functions.swapExactETHForTokens(
                    amount_out_min,
                    path,
                    WALLET_ADDRESS,
                    deadline
                ).build_transaction({
                    'from': WALLET_ADDRESS,
                    'value': web3.to_wei(amount_eth, 'ether'),
                    'nonce': web3.eth.get_transaction_count(WALLET_ADDRESS),
                })
                logging.info("Transaction built successfully.")

                # Handle gas and fee settings based on ENABLE_AUTOMATIC_FEES
                if config['ENABLE_AUTOMATIC_FEES']:
                    # Automatic mode: Do not manually set gas limit or fees
                    logging.info("Automatic fees and gas limits are enabled. Letting the Ethereum node handle everything.")
                else:
                    # Estimate gas limit manually
                    gas_limit = web3.eth.estimate_gas(txn)
                    txn['gas'] = gas_limit
                    logging.info(f"Estimated gas limit: {gas_limit}")

                    # Manual fee setting based on multipliers
                    base_fee = int(web3.eth.get_block('latest')['baseFeePerGas'] * BASE_FEE_MULTIPLIER)
                    priority_fee = int(web3.eth.max_priority_fee * PRIORITY_FEE_MULTIPLIER)

                    total_fee = int((base_fee + priority_fee) * TOTAL_FEE_MULTIPLIER)

                    txn['maxFeePerGas'] = total_fee
                    txn['maxPriorityFeePerGas'] = priority_fee

                    logging.info(f"Manual fees applied: Total Fee: {web3.from_wei(total_fee, 'gwei')} GWEI, Priority Fee: {web3.from_wei(priority_fee, 'gwei')} GWEI")

                # Sign the transaction
                signed_txn = web3.eth.account.sign_transaction(txn, private_key=WALLET_PRIVATE_KEY)

                # Send the transaction
                tx_hash = send_transaction(signed_txn)
                log_transaction({
                        "post_hash": trans_hash,
                        "buy": "YES",
                        "buy_tx": tx_hash.hex(),
                        "profit_loss": ""
                    })
                logging.info(f"TRANSACTION SENT WITH HASH: {tx_hash.hex()}")

                # Wait for the transaction to be mined and check final token balance
                final_token_balance = wait_for_balance_change(check_token_balance, token_address, expected_increase=True)
                if final_token_balance is None:
                    logging.error("Failed to detect balance change after buy.")
                    return None, tx_hash.hex(), initial_eth_balance

                # Calculate the actual tokens received
                tokens_received = final_token_balance - initial_token_balance
                logging.info(f"Tokens received: {tokens_received}")

                return tokens_received, tx_hash.hex(), initial_eth_balance, initial_price

            except Exception as e:
                retry_count += 1
                logging.error(f"Buy transaction failed on attempt {retry_count}. Error: {e}")
                logging.debug(f"Detailed transaction object: {txn}")
                logging.debug(f"Transaction data: {signed_txn.rawTransaction.hex()}")

                # Wait before retrying based on retry_count
                if retry_count < max_retries:
                    logging.info(f"Waiting {retry_delays[retry_count - 1]} seconds before retrying...")
                    time.sleep(retry_delays[retry_count - 1])

                if retry_count >= max_retries:
                    logging.error("Max retries reached. Skipping the buy transaction.")
                    log_transaction({
                        "post_hash": trans_hash,
                        "buy": "NO",
                        "sell": "NO",
                        "fail": "Buying tokens failed after retries.",
                        "profit_loss": ""
                    })
                    return None, None, None, None

    except Exception as e:
        logging.error(f"Failed to execute swap: {e}")
        return None, None, None, None
