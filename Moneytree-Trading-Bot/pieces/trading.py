import os
import json
import logging
from web3 import Web3
import yaml
from datetime import datetime, timedelta, timezone
import time
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

def retry_scam_check(token_address, retries=3, delay_seconds=10):
    for attempt in range(retries):
        scam_detected = scrape_dexanalyzer(token_address)
        if scam_detected:
            logging.warning(f"SCAM detected for token {token_address}. Retrying ({attempt + 1}/{retries}) in {delay_seconds} seconds.")
            time.sleep(delay_seconds)
        else:
            logging.info(f"No scam detected for token {token_address} on attempt {attempt + 1}. Proceeding with the buy.")
            return False  # No scam detected, proceed with buy
    logging.warning(f"SCAM detected for token {token_address} after {retries} retries. Skipping the buy.")
    return True  # Scam detected after all retries

def calculate_token_amount(eth_amount, token_price):
    logging.debug(f"Calculating token amount: ETH amount={eth_amount}, Token price={token_price}")
    return eth_amount / token_price

def get_token_price(token_address):
    logging.info(f"Fetching token price for address: {token_address}")
    token_price = None
    
    # Try getting price from Uniswap V2
    try:
        pair_address = uniswap_v2_factory.functions.getPair(WETH_ADDRESS, token_address).call()
        logging.debug(f"Uniswap V2 Pair address: {pair_address}")
        if pair_address != '0x0000000000000000000000000000000000000000':
            pair_contract = web3.eth.contract(address=pair_address, abi=uniswap_v2_pair_abi)
            reserves = pair_contract.functions.getReserves().call()
            if WETH_ADDRESS < token_address:
                reserve_weth, reserve_token = reserves[0], reserves[1]
            else:
                reserve_token, reserve_weth = reserves[0], reserves[1]
            token_price = reserve_weth / reserve_token
            logging.info(f"Token price from Uniswap V2: {token_price} WETH")
    except Exception as e:
        logging.error(f"Error fetching token price from Uniswap V2: {e}")

    # Try getting price from Uniswap V3 if not found in V2
    if token_price is None:
        try:
            pool_address = uniswap_v3_factory.functions.getPool(WETH_ADDRESS, token_address, 3000).call()
            logging.debug(f"Uniswap V3 Pool address: {pool_address}")
            if pool_address != '0x0000000000000000000000000000000000000000':
                pool_contract = web3.eth.contract(address=pool_address, abi=uniswap_v3_pool_abi)
                slot0 = pool_contract.functions.slot0().call()
                sqrt_price_x96 = slot0[0]
                token_price = (sqrt_price_x96**2) / (2**192)
                logging.info(f"Token price from Uniswap V3: {token_price} WETH")
        except Exception as e:
            logging.error(f"Error fetching token price from Uniswap V3: {e}")

    if token_price is None:
        logging.error(f"Failed to fetch token price for address: {token_address}")

    return token_price

def check_token_balance(token_address):
    try:
        token_address = Web3.to_checksum_address(token_address)
        token_contract = web3.eth.contract(address=token_address, abi=uniswap_v2_erc20_abi)
        balance = token_contract.functions.balanceOf(WALLET_ADDRESS).call()
        logging.info(f"Token balance for address {token_address}: {balance} tokens")
        return balance
    except Exception as e:
        logging.error(f"Error checking token balance: {e}")
        return None

def check_eth_balance():
    try:
        balance = web3.eth.get_balance(WALLET_ADDRESS)
        logging.info(f"ETH balance for wallet {WALLET_ADDRESS}: {web3.from_wei(balance, 'ether')} ETH")
        return balance
    except Exception as e:
        logging.error(f"Error checking ETH balance: {e}")
        return None

def wait_for_balance_change(initial_balance_func, token_address=None, expected_increase=True, max_attempts=30, delay_seconds=2):
    initial_balance = initial_balance_func(token_address) if token_address else initial_balance_func()
    for attempt in range(max_attempts):
        current_balance = initial_balance_func(token_address) if token_address else initial_balance_func()
        logging.info(f"Attempt {attempt + 1}: Current balance = {current_balance}")

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

def wait_for_approval(token_contract, token_address, amount_in_smallest_unit, max_attempts=30, delay_seconds=2):
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

def buy_token(token_address, amount_eth):
    try:
        logging.info(f"Starting buy process for token: {token_address} with {amount_eth} ETH")

        # Ensure token_address is checksummed
        token_address = Web3.to_checksum_address(token_address)
        logging.debug(f"Checksummed token address: {token_address}")

        # Run DexAnalyzer Scraper with retry logic
        scam_detected = retry_scam_check(token_address)
        if scam_detected:
            return None, None, None

        # Check initial ETH balance before buy
        initial_eth_balance = check_eth_balance()
        if initial_eth_balance is None:
            raise Exception("Failed to check initial ETH balance.")

        # Log wallet balance
        logging.info(f"Wallet ETH balance before transaction: {web3.from_wei(initial_eth_balance, 'ether')} ETH")

        # Check if the balance is sufficient
        required_balance = web3.to_wei(0.025 + amount_eth, 'ether')
        if initial_eth_balance < required_balance:
            logging.warning(f"Insufficient balance for transaction. Required: {web3.from_wei(required_balance, 'ether')} ETH")
            return None, None, initial_eth_balance

        # Check initial token balance
        initial_token_balance = check_token_balance(token_address)
        if initial_token_balance is None:
            raise Exception("Failed to check initial token balance.")

        # Determine transaction parameters
        deadline = int((datetime.now(timezone.utc) + timedelta(minutes=10)).timestamp())
        logging.debug(f"Transaction deadline: {deadline}, Slippage tolerance: {SLIPPAGE_TOLERANCE}")

        # Get token price from Uniswap
        initial_price = get_token_price(token_address)
        if initial_price is None:
            raise Exception("Token price not found on Uniswap V2 or V3.")

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

        # Estimate gas limit
        gas_limit = web3.eth.estimate_gas(txn)
        txn['gas'] = gas_limit
        logging.info(f"Estimated gas limit: {gas_limit}")

        # Fetch current gas prices
        base_fee = int(web3.eth.get_block('latest')['baseFeePerGas'] * BASE_FEE_MULTIPLIER)
        priority_fee = int(web3.eth.max_priority_fee * PRIORITY_FEE_MULTIPLIER)

        # Apply the total fee multiplier to the final fee (base + priority fee)
        total_fee = int((base_fee + priority_fee) * TOTAL_FEE_MULTIPLIER)

        # Set EIP-1559 fields
        txn['maxFeePerGas'] = total_fee
        txn['maxPriorityFeePerGas'] = priority_fee  # Priority fee remains after multiplication

        # Log the final fee values
        logging.info(f"Total gas fee (after applying multiplier): {web3.from_wei(total_fee, 'gwei')} GWEI")
        logging.info(f"Priority fee: {web3.from_wei(priority_fee, 'gwei')} GWEI")

        # Sign the transaction
        signed_txn = web3.eth.account.sign_transaction(txn, private_key=WALLET_PRIVATE_KEY)

        # Send the transaction
        tx_hash = send_transaction(signed_txn)
        logging.info(f"Transaction sent with hash: {tx_hash.hex()}")

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
        logging.error(f"Failed to execute swap: {e}")
        return None, None, None

def sell_token(token_address, token_amount, initial_eth_balance, use_moonbag=False):
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

            # Estimate gas limit for approval
            approve_gas_limit = web3.eth.estimate_gas(approve_txn)
            approve_txn['gas'] = approve_gas_limit
            logging.info(f"Estimated gas limit for approval: {approve_gas_limit}")

            # Fetch current gas price and increase slightly
            base_fee = int(web3.eth.get_block('latest')['baseFeePerGas'] * BASE_FEE_MULTIPLIER)
            priority_fee = int(web3.eth.max_priority_fee * PRIORITY_FEE_MULTIPLIER)

            # Apply the total fee multiplier to the final fee (base + priority fee)
            total_fee = int((base_fee + priority_fee) * TOTAL_FEE_MULTIPLIER)

            # Set EIP-1559 fields
            approve_txn['maxFeePerGas'] = total_fee
            approve_txn['maxPriorityFeePerGas'] = priority_fee

            signed_approve_txn = web3.eth.account.sign_transaction(approve_txn, private_key=WALLET_PRIVATE_KEY)
            approve_tx_hash = send_transaction(signed_approve_txn)
            logging.info(f"Approve transaction sent with hash: {approve_tx_hash.hex()}")

            # Wait for the approval to be confirmed and check allowance again
            if not wait_for_approval(token_contract, token_address, amount_in_smallest_unit):
                logging.error("Token approval failed or took too long.")
                return None, None

        # **Add a x-second delay before proceeding to sell**
        logging.info("Waiting x seconds after approval...")
        time.sleep(5)

        # Check initial ETH balance before the sell
        pre_sell_eth_balance = check_eth_balance()
        if pre_sell_eth_balance is None:
            raise Exception("Failed to check initial ETH balance before sell.")

        # Determine transaction parameters
        deadline = int((datetime.now(timezone.utc) + timedelta(minutes=10)).timestamp())
        amount_out_min = 0  # You can set a more realistic amount or use a slippage tolerance mechanism

        # Fetch current gas price for the sell transaction
        base_fee = int(web3.eth.get_block('latest')['baseFeePerGas'] * BASE_FEE_MULTIPLIER)
        priority_fee = int(web3.eth.max_priority_fee * PRIORITY_FEE_MULTIPLIER)

        # Apply the total fee multiplier to the final fee (base + priority fee)
        total_fee = int((base_fee + priority_fee) * TOTAL_FEE_MULTIPLIER)

        # Try the standard swapExactTokensForETH method first
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

            # Estimate gas limit
            gas_limit = web3.eth.estimate_gas(txn)
            txn['gas'] = gas_limit
            logging.info(f"Estimated gas limit: {gas_limit}")

            # Set EIP-1559 fields
            txn['maxFeePerGas'] = total_fee
            txn['maxPriorityFeePerGas'] = priority_fee

            # Sign and send the transaction
            signed_txn = web3.eth.account.sign_transaction(txn, private_key=WALLET_PRIVATE_KEY)
            tx_hash = send_transaction(signed_txn)
            logging.info(f"Sell transaction sent with hash: {tx_hash.hex()}")

        except Exception as e:
            if 'UniswapV2: K' in str(e):
                logging.warning("UniswapV2: K error occurred, retrying with swapExactTokensForETHSupportingFeeOnTransferTokens...")

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

                # Estimate gas limit
                gas_limit = web3.eth.estimate_gas(txn)
                txn['gas'] = gas_limit
                logging.info(f"Estimated gas limit: {gas_limit}")

                # Set EIP-1559 fields
                txn['maxFeePerGas'] = total_fee
                txn['maxPriorityFeePerGas'] = priority_fee

                # Sign and send the transaction
                signed_txn = web3.eth.account.sign_transaction(txn, private_key=WALLET_PRIVATE_KEY)
                tx_hash = send_transaction(signed_txn)
                logging.info(f"Sell transaction (with fee-on-transfer support) sent with hash: {tx_hash.hex()}")

        # Wait for the transaction to be mined and check final ETH balance
        logging.info(f"INITIAL: {initial_eth_balance} ETH")
        final_eth_balance = wait_for_balance_change(check_eth_balance, expected_increase=True)
        logging.info(f"FINAL: {final_eth_balance} ETH")
        if final_eth_balance is None:
            logging.error("Failed to detect balance change after sell.")
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

        return tx_hash.hex(), profit_loss

    except Exception as e:
        logging.error(f"Failed to execute swap: {e}")
        return None, None
