import json
from web3 import Web3
import logging
import yaml
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Get the absolute path of the parent directory
parent_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

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

# Initialize web3
ETEREUM_NODE_URL = config['ETEREUM_NODE_URL']
web3 = Web3(Web3.HTTPProvider(ETEREUM_NODE_URL))

# Define addresses
WETH_ADDRESS = '0xC02aaA39b223FE8D0A0E5C4F27eAD9083C756Cc2'
UNISWAP_V2_FACTORY_ADDRESS = '0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f'
UNISWAP_V3_FACTORY_ADDRESS = '0x1F98431c8aD98523631AE4a59f267346ea31F984'  # Uniswap V3 Factory Address
CHAINLINK_ETH_USD_FEED = '0x5f4ec3df9cbd43714fe2740f5e3616155c5b8419'

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
    pair_address = uniswap_v2_factory.functions.getPair(Web3.to_checksum_address(token_address), Web3.to_checksum_address(WETH_ADDRESS)).call()
    
    if pair_address == '0x0000000000000000000000000000000000000000':
        logging.info("No pair address found on Uniswap V2.")
        return None, None

    logging.info(f"Pair address found: {pair_address}")
    pair_contract = web3.eth.contract(address=Web3.to_checksum_address(pair_address), abi=uniswap_v2_pair_abi)
    reserves = pair_contract.functions.getReserves().call()
    
    reserve0, reserve1 = reserves[0], reserves[1]
    token0 = pair_contract.functions.token0().call()

    if Web3.to_checksum_address(token_address) == Web3.to_checksum_address(token0):
        reserve_token = reserve0
        reserve_weth = reserve1
    else:
        reserve_token = reserve1
        reserve_weth = reserve0

    adjusted_reserve_token = reserve_token / (10 ** token_decimals)
    adjusted_reserve_weth = reserve_weth / (10 ** 18)

    logging.info(f"Reserves - Token: {adjusted_reserve_token}, WETH: {adjusted_reserve_weth}")

    if adjusted_reserve_token == 0:
        logging.error("Adjusted reserve token is zero, cannot calculate token price.")
        return None, None

    token_price = adjusted_reserve_weth / adjusted_reserve_token
    logging.info(f"Token price on Uniswap V2: {token_price} ETH")
    return token_price, pair_address

def get_uniswap_v3_price(token_address, token_decimals):
    fee_tiers = [500, 3000, 10000]
    
    for fee in fee_tiers:
        try:
            # Fetch pool address from Uniswap V3 Factory contract
            pool_address = uniswap_v3_factory.functions.getPool(Web3.to_checksum_address(token_address), Web3.to_checksum_address(WETH_ADDRESS), fee).call()
            
            if pool_address != '0x0000000000000000000000000000000000000000':
                pool_contract = web3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=uniswap_v3_pool_abi)
                slot0 = pool_contract.functions.slot0().call()
                sqrtPriceX96 = slot0[0]
                
                # Fetch liquidity and verify it's above a reasonable threshold
                liquidity = pool_contract.functions.liquidity().call()
                if liquidity < 10**6:  # Set a threshold for minimum liquidity
                    logging.warning(f"Liquidity too low in Uniswap V3 pool (fee tier {fee}): {liquidity}")
                    continue
                
                # Correct calculation for token price in WETH
                token_price_in_weth = (sqrtPriceX96 ** 2) / (2 ** 192)
                
                # Since the price is in terms of WETH per token, invert if needed
                token_price = 1 / token_price_in_weth
                
                logging.info(f"Token price on Uniswap V3 (fee tier {fee}): {token_price} WETH")
                
                # Check for unreasonable prices (e.g., greater than a reasonable range)
                if token_price > 1000 or token_price < 0.0000001:
                    logging.warning(f"Token price {token_price} WETH seems unrealistic. Skipping this pool.")
                    continue
                
                return token_price, pool_address
        except Exception as e:
            logging.error(f"Error fetching Uniswap V3 price for fee tier {fee}: {e}")
    
    logging.info("No reliable pool address found on Uniswap V3.")
    return None, None

def calculate_market_cap(token_address):
    eth_price_in_usd = get_eth_price_in_usd()
    if eth_price_in_usd is None:
        logging.info("Cannot calculate market cap without ETH price.")
        return None

    name, symbol, decimals, total_supply = get_token_details(token_address)
    token_price, pair_address = get_uniswap_v2_price(token_address, decimals)
    
    if token_price is None:
        token_price, pair_address = get_uniswap_v3_price(token_address, decimals)

    if token_price is not None:
        market_cap_eth = total_supply * token_price
        market_cap_usd = market_cap_eth * eth_price_in_usd
        logging.info(f"Market Cap for {name} ({symbol}) - ETH: {market_cap_eth}, USD: {market_cap_usd}")
        return market_cap_usd
    else:
        logging.info("Token price not available on Uniswap V2 or V3.")
        return None

def format_market_cap(market_cap):
    if market_cap >= 1_000_000_000:
        return f"{market_cap / 1_000_000_000:.1f}B"
    elif market_cap >= 1_000_000:
        return f"{market_cap / 1_000_000:.1f}M"
    elif market_cap >= 1_000:
        return f"{market_cap / 1_000:.1f}K"
    else:
        return str(market_cap)
