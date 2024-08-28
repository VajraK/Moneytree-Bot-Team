# Helper functions to update different sections of the config
def update_ethereum_settings(config, form):
    config['ETEREUM_NODE_URL'] = form.get('ETEREUM_NODE_URL', config.get('ETEREUM_NODE_URL'))
    config['WETH_ADDRESS'] = form.get('WETH_ADDRESS', config.get('WETH_ADDRESS'))
    config['UNISWAP_V2_FACTORY_ADDRESS'] = form.get('UNISWAP_V2_FACTORY_ADDRESS', config.get('UNISWAP_V2_FACTORY_ADDRESS'))
    config['UNISWAP_V3_FACTORY_ADDRESS'] = form.get('UNISWAP_V3_FACTORY_ADDRESS', config.get('UNISWAP_V3_FACTORY_ADDRESS'))
    config['CHAINLINK_ETH_USD_FEED'] = form.get('CHAINLINK_ETH_USD_FEED', config.get('CHAINLINK_ETH_USD_FEED'))

def update_wallet_config(config, form):
    config['WALLET_PRIVATE_KEY'] = form.get('WALLET_PRIVATE_KEY', config.get('WALLET_PRIVATE_KEY'))

def update_trading_parameters(config, form):
    # Helper function to safely convert strings to numbers
    def convert_to_number(value, default):
        try:
            if '.' in value:  # If it contains a decimal, convert to float
                return float(value)
            return int(value)  # Otherwise, convert to int
        except (ValueError, TypeError):
            return default  # If conversion fails, return the default value
    config['AMOUNT_OF_ETH'] = convert_to_number(form.get('AMOUNT_OF_ETH', config.get('AMOUNT_OF_ETH')), config.get('AMOUNT_OF_ETH'))
    config['MOONBAG'] = convert_to_number(form.get('MOONBAG', config.get('MOONBAG')), config.get('MOONBAG'))
    config['BASE_FEE_MULTIPLIER'] = convert_to_number(form.get('BASE_FEE_MULTIPLIER', config.get('BASE_FEE_MULTIPLIER')), config.get('BASE_FEE_MULTIPLIER'))
    config['PRIORITY_FEE_MULTIPLIER'] = convert_to_number(form.get('PRIORITY_FEE_MULTIPLIER', config.get('PRIORITY_FEE_MULTIPLIER')), config.get('PRIORITY_FEE_MULTIPLIER'))
    config['TOTAL_FEE_MULTIPLIER'] = convert_to_number(form.get('TOTAL_FEE_MULTIPLIER', config.get('TOTAL_FEE_MULTIPLIER')), config.get('TOTAL_FEE_MULTIPLIER'))
    config['SLIPPAGE_TOLERANCE'] = convert_to_number(form.get('SLIPPAGE_TOLERANCE', config.get('SLIPPAGE_TOLERANCE')), config.get('SLIPPAGE_TOLERANCE'))
    config['PRICE_INCREASE_THRESHOLD'] = convert_to_number(form.get('PRICE_INCREASE_THRESHOLD', config.get('PRICE_INCREASE_THRESHOLD')), config.get('PRICE_INCREASE_THRESHOLD'))
    config['PRICE_DECREASE_THRESHOLD'] = convert_to_number(form.get('PRICE_DECREASE_THRESHOLD', config.get('PRICE_DECREASE_THRESHOLD')), config.get('PRICE_DECREASE_THRESHOLD'))
    config['NO_CHANGE_THRESHOLD'] = convert_to_number(form.get('NO_CHANGE_THRESHOLD', config.get('NO_CHANGE_THRESHOLD')), config.get('NO_CHANGE_THRESHOLD'))
    config['NO_CHANGE_TIME_MINUTES'] = convert_to_number(form.get('NO_CHANGE_TIME_MINUTES', config.get('NO_CHANGE_TIME_MINUTES')), config.get('NO_CHANGE_TIME_MINUTES'))
    config['MIN_MARKET_CAP'] = convert_to_number(form.get('MIN_MARKET_CAP', config.get('MIN_MARKET_CAP')), config.get('MIN_MARKET_CAP'))
    config['MAX_MARKET_CAP'] = convert_to_number(form.get('MAX_MARKET_CAP', config.get('MAX_MARKET_CAP')), config.get('MAX_MARKET_CAP'))


def update_telegram_settings(config, form):
    config['MTB_TELEGRAM_BOT_TOKEN'] = form.get('MTB_TELEGRAM_BOT_TOKEN', config.get('MTB_TELEGRAM_BOT_TOKEN'))
    config['MTB_CHAT_ID'] = form.get('MTB_CHAT_ID', config.get('MTB_CHAT_ID'))
    config['MTdB_TELEGRAM_BOT_TOKEN'] = form.get('MTdB_TELEGRAM_BOT_TOKEN', config.get('MTdB_TELEGRAM_BOT_TOKEN'))
    config['MTdB_CHAT_ID'] = form.get('MTdB_CHAT_ID', config.get('MTdB_CHAT_ID'))

def update_feature_toggles(config, form):
    config['SEND_TELEGRAM_MESSAGES'] = 'true' if 'SEND_TELEGRAM_MESSAGES' in form else 'false'
    config['ALLOW_SWAP_MESSAGES_ONLY'] = 'true' if 'ALLOW_SWAP_MESSAGES_ONLY' in form else 'false'
    config['ALLOW_AGGREGATED_MESSAGES_ALSO'] = 'true' if 'ALLOW_AGGREGATED_MESSAGES_ALSO' in form else 'false'
    config['ALLOW_MTDB_INTERACTION'] = 'true' if 'ALLOW_MTDB_INTERACTION' in form else 'false'
    config['ALLOW_MULTIPLE_TRANSACTIONS'] = 'true' if 'ALLOW_MULTIPLE_TRANSACTIONS' in form else 'false'
    config['ENABLE_MARKET_CAP_FILTER'] = 'true' if 'ENABLE_MARKET_CAP_FILTER' in form else 'false'
    config['ENABLE_PRICE_CHANGE_CHECKER'] = 'true' if 'ENABLE_PRICE_CHANGE_CHECKER' in form else 'false'
    config['ENABLE_TRADING'] = 'true' if 'ENABLE_TRADING' in form else 'false'
    config['ENABLE_AUTOMATIC_FEES'] = 'true' if 'ENABLE_AUTOMATIC_FEES' in form else 'false'
    
    # Convert these 'true'/'false' strings back to actual booleans
    for key in config:
        if config[key] == 'true':
            config[key] = True
        elif config[key] == 'false':
            config[key] = False

def update_addresses_to_monitor(config, form):
    addresses = form.getlist('addresses')
    names = form.getlist('names')
    config['ADDRESSES_TO_MONITOR'] = {addr: name for addr, name in zip(addresses, names) if addr and name}