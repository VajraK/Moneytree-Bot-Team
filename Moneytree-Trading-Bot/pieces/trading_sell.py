import logging
import os
import yaml
import json
import time
from datetime import datetime, timedelta, timezone
from web3 import Web3
from pieces.trading_utils import (
    send_transaction
)
from pieces.statistics import log_transaction
from pieces.uniswap import get_approval_amount, get_swap_amount

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

# Amount of ETH
AMOUNT_OF_ETH = config['AMOUNT_OF_ETH']

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

def sell_token(token_address, token_amount, trans_hash, use_moonbag=False):
    max_retries = 30  # Maximum number of retries
    retry_count = 0  # Track the number of retries

    # Retry delays
    retry_delays = [5] * max_retries

    # Flag to check if it's the first attempt
    first_attempt = True

    while retry_count < max_retries:
        try:
            if first_attempt:
                logging.info(f"Starting sell process for token: {token_address} with amount: {token_amount}")

            # Ensure token_address is checksummed
            if first_attempt:
                token_address = Web3.to_checksum_address(token_address)
                logging.debug(f"Checksummed token address: {token_address}")

            # Apply moonbag logic if use_moonbag is True and MOONBAG is defined
            if first_attempt:
                if use_moonbag:
                    MOONBAG = float(config['MOONBAG'])
                    token_amount = token_amount * (1 - MOONBAG)
                    logging.info(f"Applying moonbag logic. New token amount to sell: {token_amount}")

            # Convert token amount to smallest unit
            if first_attempt:
                amount_in_smallest_unit = int(token_amount)  # Assuming token_amount is already in smallest unit format
                logging.debug(f"Token amount in smallest unit: {amount_in_smallest_unit}")

            # Get the token contract
            if first_attempt:
                token_contract = web3.eth.contract(address=token_address, abi=uniswap_v2_erc20_abi)

            # Check the token balance
            wallet_balance = token_contract.functions.balanceOf(WALLET_ADDRESS).call()
            logging.info(f"Wallet token balance: {wallet_balance} tokens")

            if wallet_balance < amount_in_smallest_unit:
                raise Exception(f"Insufficient token balance. Available: {wallet_balance}, Required: {amount_in_smallest_unit}")

            # Check current allowance
            allowance = token_contract.functions.allowance(WALLET_ADDRESS, UNISWAP_V2_ROUTER_ADDRESS).call()
            logging.info(f"Current token allowance: {allowance} tokens")

            if allowance < amount_in_smallest_unit:
                logging.info(f"Approving Uniswap router to spend {amount_in_smallest_unit} tokens")
                approve_txn = token_contract.functions.approve(
                    UNISWAP_V2_ROUTER_ADDRESS,
                    amount_in_smallest_unit
                ).build_transaction({
                    'from': WALLET_ADDRESS,
                    'nonce': web3.eth.get_transaction_count(WALLET_ADDRESS),
                })

                # Handle gas limit and fees for approval transaction
                if config['ENABLE_AUTOMATIC_FEES']:
                    logging.info(f"Automatic fees are enabled, not specifying gas limits or fees.")
                else:
                    # Estimate gas limit for approval
                    approve_gas_limit = web3.eth.estimate_gas(approve_txn)
                    approve_txn['gas'] = approve_gas_limit
                    logging.info(f"Estimated gas limit for approval: {approve_gas_limit}")

                    # Manual fee setting based on multipliers
                    base_fee = int(web3.eth.get_block('latest')['baseFeePerGas'] * BASE_FEE_MULTIPLIER)
                    priority_fee = int(web3.eth.max_priority_fee * PRIORITY_FEE_MULTIPLIER)
                    total_fee = int((base_fee + priority_fee) * TOTAL_FEE_MULTIPLIER)

                    approve_txn['maxFeePerGas'] = total_fee
                    approve_txn['maxPriorityFeePerGas'] = priority_fee

                    logging.info(f"Manual fees applied for approval: Total Fee: {web3.from_wei(total_fee, 'gwei')} GWEI, Priority Fee: {web3.from_wei(priority_fee, 'gwei')} GWEI")

                # Sign and send the approval transaction
                signed_approve_txn = web3.eth.account.sign_transaction(approve_txn, private_key=WALLET_PRIVATE_KEY)
                approve_tx_hash = send_transaction(signed_approve_txn)
                logging.info(f"APPROVE TRANSACTION SENT WITH HASH: {approve_tx_hash.hex()}")

                # Wait for the approval to be confirmed and check allowance again
                approved_amount = get_approval_amount(approve_tx_hash)
                if approved_amount is None or approved_amount < amount_in_smallest_unit:
                    logging.error("Token approval failed or took too long.")
                    log_transaction({
                        "post_hash": trans_hash,
                        "sell": "NO",
                        "fail": "Token sell approval failed.",
                        "profit_loss": ""
                    })
                    return None, None

            # Add a delay only if it's the first attempt
            if first_attempt:
                logging.info("Waiting 5 seconds after approval...")
                time.sleep(5)
                first_attempt = False

            # Define the transaction parameters
            deadline = int((datetime.now(timezone.utc) + timedelta(minutes=10)).timestamp())
            amount_out_min = 0  # Set slippage tolerance here if needed

            # Attempt normal sell transaction
            txn = uniswap_v2_router.functions.swapExactTokensForETH(
                amount_in_smallest_unit,
                amount_out_min,
                [token_address, WETH_ADDRESS],
                Web3.to_checksum_address(WALLET_ADDRESS),
                deadline
            ).build_transaction({
                'from': WALLET_ADDRESS,
                'nonce': web3.eth.get_transaction_count(WALLET_ADDRESS),
            })

            logging.info("Normal sell transaction built successfully.")

            # Handle gas limit and fees for sell transaction
            if config['ENABLE_AUTOMATIC_FEES']:
                logging.info(f"Automatic fees are enabled, not specifying gas limits or fees.")
            else:
                # Estimate gas limit
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

            # Sign and send the transaction
            signed_txn = web3.eth.account.sign_transaction(txn, private_key=WALLET_PRIVATE_KEY)
            tx_hash = send_transaction(signed_txn)
            logging.info(f"SELL TRANSACTION SENT WITH HASH: {tx_hash.hex()}")
            break  # Exit retry loop on success

        except Exception as e:
            logging.error(f"Sell transaction failed on attempt {retry_count + 1}. Error: {e}")

            # Check if error is 'UniswapV2: K'
            if 'UniswapV2: K' in str(e):
                logging.warning("UniswapV2: K error occurred, attempting fallback sell.")

                try:
                    # Attempt fallback sell transaction
                    txn = uniswap_v2_router.functions.swapExactTokensForETHSupportingFeeOnTransferTokens(
                        amount_in_smallest_unit,
                        amount_out_min,
                        [token_address, WETH_ADDRESS],
                        WALLET_ADDRESS,
                        deadline
                    ).build_transaction({
                        'from': WALLET_ADDRESS,
                        'nonce': web3.eth.get_transaction_count(WALLET_ADDRESS),
                    })

                    logging.info("Fallback sell transaction built successfully.")

                    # Handle gas limit and fees for fallback sell transaction
                    if config['ENABLE_AUTOMATIC_FEES']:
                        logging.info(f"Automatic fees are enabled, not specifying gas limits or fees.")
                    else:
                        # Estimate gas limit
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

                    # Sign and send the fallback transaction
                    signed_txn = web3.eth.account.sign_transaction(txn, private_key=WALLET_PRIVATE_KEY)
                    tx_hash = send_transaction(signed_txn)
                    logging.info(f"FALLBACK SELL TRANSACTION SENT WITH HASH: {tx_hash.hex()}")
                    break  # Exit retry loop on fallback success

                except Exception as fallback_e:
                    logging.error(f"Fallback sell transaction failed. Error: {fallback_e}")

            # Increment retry count and delay before retrying
            retry_count += 1
            if retry_count < max_retries:
                logging.info(f"Waiting {retry_delays[retry_count - 1]} seconds before retrying...")
                time.sleep(retry_delays[retry_count - 1])

            # If max retries reached, log and exit
            if retry_count >= max_retries:
                logging.error("Max retries reached. Skipping the sell transaction.")
                log_transaction({
                    "post_hash": trans_hash,
                    "sell": "NO",
                    "fail": "Selling token failed.",
                    "profit_loss": ""
                })
                return None, None

    # Wait for the transaction to be mined and check final ETH balance
    received_eth = get_swap_amount(tx_hash, WETH_ADDRESS)
    logging.info(f"Final ETH Balance: {received_eth} ETH")
    if received_eth is None:
        logging.error("Failed to detect received ETH after sell.")
        log_transaction({
            "post_hash": trans_hash,
            "sell": "XXX",
            "fail": "Could not detect received ETH after sell.",
            "profit_loss": ""
        })
        return None, None

    # Calculate profit/loss by comparing final ETH balance after sell with initial ETH balance before buy
    try:
        # Ensure balances are in the same unit for calculation
        received_eth_in_ether = float(web3.from_wei(received_eth, 'ether'))  
        bought_for_in_ether = float(AMOUNT_OF_ETH)

        # Calculate profit or loss
        profit_loss = received_eth_in_ether - bought_for_in_ether
        logging.info(f"Total Profit/Loss: {profit_loss:.18f} ETH")
    except Exception as e:
        logging.error(f"Failed to calculate profit/loss: {e}")
        profit_loss = "0"

    # Log the transaction
    log_transaction({
        "post_hash": trans_hash,
        "sell": "YES",
        "sell_tx": tx_hash.hex(),
        "profit_loss": f"{profit_loss:.18f}"
    })

    return tx_hash.hex(), profit_loss
