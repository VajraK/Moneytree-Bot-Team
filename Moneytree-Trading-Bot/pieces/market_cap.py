import logging
from pieces.uniswap import get_eth_price_in_usd,  get_uniswap_v2_price, get_uniswap_v3_price

def calculate_market_cap(token_address, name, symbol, total_supply, decimals):
    eth_price_in_usd = get_eth_price_in_usd()
    if eth_price_in_usd is None:
        logging.info("Cannot calculate market cap without ETH price.")
        return None

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
