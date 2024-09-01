import logging
import os
import yaml
import json
import time
from datetime import datetime, timedelta, timezone
from web3 import Web3
from pieces.trading_utils import (
    check_eth_balance,
    wait_for_approval,
    wait_for_balance_change,
    send_transaction
)
from pieces.statistics import log_transaction

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

def sell_token(token_address, token_amount, initial_eth_balance, trans_hash, use_moonbag=False):
    max_retries = 25  # Maximum number of retries
    gas_multiplier_increment = 1.2  # Increment to apply to gas prices for retries
    retry_count = 0  # Track the number of retries

    # Retry delays
    retry_delays = [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5]

    try:
        logging.info(f"Starting sell process for token: {token_address} with amount: {token_amount}")

        # Ensure token_address is checksummed
        token_address = Web3.to_checksum_address(token_address)
        logging.debug(f"Checksummed token address: {token_address}")

        # Apply moonbag logic if use_moonbag is True and MOONBAG is defined
        if use_moonbag:
            MOONBAG = float(config['MOONBAG'])
            token_amount = token_amount * (1 - MOONBAG)
            logging.info(f"Applying moonbag logic. New token amount to sell: {token_amount}")

        # Convert token amount to smallest unit
        amount_in_smallest_unit = int(token_amount)  # Assuming token_amount is already in smallest unit format
        logging.info(f"Token amount in smallest unit: {amount_in_smallest_unit}")

        # Get the token contract
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
            logging.info(f"Approve transaction sent with hash: {approve_tx_hash.hex()}")

            # Wait for the approval to be confirmed and check allowance again
            if not wait_for_approval(token_contract, token_address, amount_in_smallest_unit):
                logging.error("Token approval failed or took too long.")
                log_transaction({
                    "post_hash": trans_hash,
                    "sell": "NO",
                    "fail": "Token sell approval failed.",
                    "profit_loss": ""
                })
                return None, None

        # **Add a delay before proceeding to sell**
        logging.info("Waiting 5 seconds after approval...")
        time.sleep(5)

        # Check initial ETH balance before the sell
        pre_sell_eth_balance = check_eth_balance()
        if pre_sell_eth_balance is None:
            raise Exception("Failed to check initial ETH balance before sell.")

        # Define the transaction parameters
        deadline = int((datetime.now(timezone.utc) + timedelta(minutes=10)).timestamp())
        amount_out_min = 0  # Set slippage tolerance here if needed

        while retry_count < max_retries:
            try:
                # Create sell transaction
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
                logging.info("Sell transaction built successfully.")

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
                logging.info(f"Sell transaction sent with hash: {tx_hash.hex()}")
                break  # Exit retry loop on success

            except Exception as e:
                retry_count += 1
                logging.error(f"Sell transaction failed on attempt {retry_count}. Error: {e}")

                # Wait before retrying based on retry_count
                if retry_count < max_retries:
                    logging.info(f"Waiting {retry_delays[retry_count - 1]} seconds before retrying...")
                    time.sleep(retry_delays[retry_count - 1])

                # If fallback is necessary due to 'UniswapV2: K' error
                if 'UniswapV2: K' in str(e):
                    logging.warning("UniswapV2: K error occurred, retrying with swapExactTokensForETHSupportingFeeOnTransferTokens...")

                    # Retry logic for fallback method
                    fallback_retries = 0
                    while fallback_retries < max_retries:
                        try:
                            # Adjust gas fees for fallback retry
                            base_fee = int(web3.eth.get_block('latest')['baseFeePerGas'] * BASE_FEE_MULTIPLIER)
                            priority_fee = int(web3.eth.max_priority_fee * PRIORITY_FEE_MULTIPLIER)
                            total_fee = int((base_fee + priority_fee) * (TOTAL_FEE_MULTIPLIER * (gas_multiplier_increment ** fallback_retries)))

                            # Fallback to swapExactTokensForETHSupportingFeeOnTransferTokens
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

                            # Handle gas limit and fees for fallback transaction
                            if config['ENABLE_AUTOMATIC_FEES']:
                                logging.info(f"Automatic fees are enabled, not specifying gas limits or fees.")
                            else:
                                # Estimate gas limit for fallback transaction
                                gas_limit = web3.eth.estimate_gas(txn)
                                txn['gas'] = gas_limit
                                logging.info(f"Fallback transaction estimated gas limit: {gas_limit}")

                                # Set EIP-1559 fields for fallback transaction
                                txn['maxFeePerGas'] = total_fee
                                txn['maxPriorityFeePerGas'] = priority_fee

                            # Sign and send the fallback transaction
                            signed_txn = web3.eth.account.sign_transaction(txn, private_key=WALLET_PRIVATE_KEY)
                            tx_hash = send_transaction(signed_txn)
                            logging.info(f"Fallback sell transaction sent with hash: {tx_hash.hex()}")
                            break  # Exit fallback retry loop on success
                        except Exception as fallback_e:
                            fallback_retries += 1
                            logging.error(f"Fallback sell transaction failed on attempt {fallback_retries}. Error: {fallback_e}")

                    if fallback_retries >= max_retries:
                        logging.error("Max retries for fallback transaction reached. Skipping the sell transaction.")
                        log_transaction({
                            "post_hash": trans_hash,
                            "sell": "NO",
                            "fail": "Special selling of token failed.",
                            "profit_loss": ""
                        })
                        return None, None

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
        logging.info(f"INITIAL: {initial_eth_balance} ETH")
        final_eth_balance = wait_for_balance_change(check_eth_balance, expected_increase=True)
        logging.info(f"FINAL: {final_eth_balance} ETH")
        if final_eth_balance is None:
            logging.error("Failed to detect balance change after sell.")
            log_transaction({
                "post_hash": trans_hash,
                "sell": "XXX",
                "fail": "Could not detect change in ETH balance after sell.",
                "profit_loss": ""
            })
            return tx_hash.hex(), None

        # Calculate profit/loss by comparing final ETH balance after sell with initial ETH balance before buy
        try:
            logging.info(f"Calculating profit/loss: initial_eth_balance = {initial_eth_balance}, final_eth_balance = {final_eth_balance}")

            # Ensure balances are in the same unit for calculation
            initial_eth_balance_in_ether = web3.from_wei(initial_eth_balance, 'ether')
            final_eth_balance_in_ether = web3.from_wei(final_eth_balance, 'ether')

            # Calculate profit or loss
            profit_loss = final_eth_balance_in_ether - initial_eth_balance_in_ether
            logging.info(f"Total Profit/Loss: {profit_loss:.18f} ETH")
        except Exception as e:
            logging.error(f"Failed to calculate profit/loss: {e}")
            profit_loss = "0"

        # Statistics
        log_transaction({
            "post_hash": trans_hash,
            "sell": "YES",
            "sell_tx": tx_hash.hex(),
            "profit_loss": f"{profit_loss:.18f}"
        })

        return tx_hash.hex(), profit_loss

    except Exception as e:
        logging.error(f"Failed to execute swap: {e}")
        return None, None
