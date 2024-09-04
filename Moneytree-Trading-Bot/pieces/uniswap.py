import logging
from web3 import Web3
import os
import json
import yaml
from web3.exceptions import TransactionNotFound
import time


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

# Define addresses
WETH_ADDRESS = config['WETH_ADDRESS']
UNISWAP_V2_FACTORY_ADDRESS = config['UNISWAP_V2_FACTORY_ADDRESS']
UNISWAP_V3_FACTORY_ADDRESS = config['UNISWAP_V3_FACTORY_ADDRESS']
CHAINLINK_ETH_USD_FEED = config['CHAINLINK_ETH_USD_FEED']

# Load ABIs
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

chainlink_price_feed_abi = json.loads('[{"inputs":[],"name":"latestRoundData","outputs":[{"internalType":"uint80","name":"roundId","type":"uint80"},{"internalType":"int256","name":"answer","type":"int256"},{"internalType":"uint256","name":"startedAt","type":"uint256"},{"internalType":"uint256","name":"updatedAt","type":"uint256"},{"internalType":"uint80","name":"answeredInRound","type":"uint80"}],"stateMutability":"view","type":"function"}]')

# Create contract instances
uniswap_v2_factory = web3.eth.contract(address=Web3.to_checksum_address(UNISWAP_V2_FACTORY_ADDRESS), abi=uniswap_v2_factory_abi)
uniswap_v3_factory = web3.eth.contract(address=Web3.to_checksum_address(UNISWAP_V3_FACTORY_ADDRESS), abi=uniswap_v3_factory_abi)
chainlink_price_feed = web3.eth.contract(address=Web3.to_checksum_address(CHAINLINK_ETH_USD_FEED), abi=chainlink_price_feed_abi)

def get_eth_price_in_usd():
    latest_round_data = chainlink_price_feed.functions.latestRoundData().call()
    eth_price_in_usd = latest_round_data[1] / 1e8  # Chainlink prices have 8 decimals
    logging.info(f"ETH price in USD: {eth_price_in_usd}")
    return eth_price_in_usd

def get_token_details(token_address):
    token_contract = web3.eth.contract(address=Web3.to_checksum_address(token_address), abi=uniswap_v2_erc20_abi)
    name = token_contract.functions.name().call()
    symbol = token_contract.functions.symbol().call()
    decimals = token_contract.functions.decimals().call()
    total_supply = token_contract.functions.totalSupply().call() / (10 ** decimals)
    logging.info(f"Token details - Name: {name}, Symbol: {symbol}, Decimals: {decimals}, Total Supply: {total_supply}")
    return name, symbol, decimals, total_supply

def get_uniswap_v2_price(token_address, token_decimals):
    try:
        # Fetch pair address from Uniswap V2 Factory contract
        pair_address = uniswap_v2_factory.functions.getPair(Web3.to_checksum_address(token_address), Web3.to_checksum_address(WETH_ADDRESS)).call()

        if pair_address == '0x0000000000000000000000000000000000000000':
            logging.warning(f"Uniswap V2 pair not found for token {token_address} and WETH.")
            return None, None

        # Create pair contract instance
        pair_contract = web3.eth.contract(address=Web3.to_checksum_address(pair_address), abi=uniswap_v2_pair_abi)

        # Fetch reserves from the pair contract
        reserves = pair_contract.functions.getReserves().call()
        reserve_weth, reserve_token = reserves[0], reserves[1]

        # Determine which reserve is for WETH and which is for the token
        if Web3.to_checksum_address(token_address) < Web3.to_checksum_address(WETH_ADDRESS):
            reserve_token, reserve_weth = reserves[0], reserves[1]
        else:
            reserve_weth, reserve_token = reserves[0], reserves[1]

        # Adjust reserves
        adjusted_reserve_token = reserve_token / (10 ** token_decimals)
        adjusted_reserve_weth = reserve_weth / (10 ** 18)

        if adjusted_reserve_token == 0 or adjusted_reserve_weth == 0:
            logging.warning(f"Reserves are zero for token {token_address} and WETH in Uniswap V2 pair.")
            return None, None

        # Calculate price
        token_price = adjusted_reserve_weth / adjusted_reserve_token
        return token_price, pair_address

    except Exception as e:
        logging.error(f"Error fetching Uniswap V2 price for token {token_address}: {e}")
        return None, None

def get_uniswap_v3_price(token_address, token_decimals):
    fee_tiers = [500, 3000, 10000]
    
    for fee in fee_tiers:
        try:
            # Fetch pool address from Uniswap V3 Factory contract
            pool_address = uniswap_v3_factory.functions.getPool(Web3.to_checksum_address(token_address), Web3.to_checksum_address(WETH_ADDRESS), fee).call()

            if pool_address != '0x0000000000000000000000000000000000000000':
                # Create pool contract instance
                pool_contract = web3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=uniswap_v3_pool_abi)

                # Fetch slot0 from the pool contract
                slot0 = pool_contract.functions.slot0().call()
                sqrtPriceX96 = slot0[0]

                # Calculate token price
                token_price = (sqrtPriceX96 ** 2 / (2 ** 192)) * (10 ** token_decimals) / (10 ** 18)
                return token_price, pool_address
            else:
                logging.warning(f"Uniswap V3 pool not found for token {token_address}, WETH, and fee tier {fee}.")
        except Exception as e:
            logging.error(f"Error fetching Uniswap V3 price for token {token_address} and fee tier {fee}: {e}")
    
    logging.warning(f"Uniswap V3 price not available for token {token_address} in any fee tier.")
    return None, None

def get_swap_amount(tx_hash, token_contract_address, max_retries=90, delay=2):
    retries = 0
    while retries < max_retries:
        try:
            # Attempt to get the transaction receipt
            tx_receipt = web3.eth.get_transaction_receipt(tx_hash)
            
            # Log successful retrieval of the transaction receipt
            logging.info(f"Transaction receipt found on try {retries + 1}.")
            
            # If successful, check for token swap events (Transfer method signature: 0xddf252ad)
            token_transfers = [log for log in tx_receipt.logs if log['topics'][0].hex() == Web3.keccak(text="Transfer(address,address,uint256)").hex()]
            
            if not token_transfers:
                    logging.warning(f"No token transfers found in transaction {tx_hash}.")
                    return "No token transfers found in this transaction"
            
            # Log the fact that we found two or more swap events
            logging.info(f"Token transfers found: {len(token_transfers)} transfers.")

            total_token_amount = 0
            
            # Loop through all transfers and sum the amount for the specified token
            for transfer in token_transfers:
                contract_address = transfer['address']
                    
                if token_contract_address and web3.to_checksum_address(contract_address) != web3.to_checksum_address(token_contract_address):
                    # Skip if the contract address doesn't match the specified token contract
                    continue
                    
                token_amount = int.from_bytes(transfer['data'], byteorder='big')
                total_token_amount += token_amount
                
            # Log the total token amount for the specified token
            logging.info(f"Total token amount found for {token_contract_address}: {total_token_amount}")
                
            return total_token_amount  # Return the total token amount

        except TransactionNotFound:
            # Log retry attempt and wait before trying again
            retries += 1
            logging.warning(f"Transaction {tx_hash} not found on try {retries}. Retrying in {delay} seconds...")
            time.sleep(delay)  # Wait for the specified delay before retrying

    # After max_retries attempts, log and return None if transaction still not found
    logging.error(f"Transaction {tx_hash} not found after {max_retries} attempts.")
    return None

def get_approval_amount(tx_hash, max_retries=90, delay=2):
    retries = 0
    while retries < max_retries:
        try:
            # Attempt to get the transaction receipt
            tx_receipt = web3.eth.get_transaction_receipt(tx_hash)
            
            # Log successful retrieval of the transaction receipt
            logging.info(f"Transaction receipt found on try {retries + 1} for tx: {tx_hash}")
            
            # Check for Approval event (Approval method signature: 0x8c5be1e5)
            approval_logs = [log for log in tx_receipt.logs if log['topics'][0].hex() == Web3.keccak(text="Approval(address,address,uint256)").hex()]
            
            if not approval_logs:
                logging.warning(f"No approval events found in transaction {tx_hash}.")
                return "No approvals found in this transaction"
            
            # Decode approval event data
            for approval in approval_logs:
                approval_amount = int.from_bytes(approval['data'], byteorder='big')
                
                # Log the found approval amount
                logging.info(f"Approval amount found: {approval_amount}")
                
                return approval_amount  # Return the approval amount if found

        except TransactionNotFound:
            # Log retry attempt and wait before trying again
            retries += 1
            logging.warning(f"Transaction {tx_hash} not found on try {retries}. Retrying in {delay} seconds...")
            time.sleep(delay)  # Wait for the specified delay before retrying

    # After max_retries attempts, log and return None if transaction still not found
    logging.error(f"Transaction {tx_hash} not found after {max_retries} attempts.")
    return None