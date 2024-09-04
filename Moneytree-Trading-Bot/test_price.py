import unittest
from web3 import Web3
from pieces.uniswap import get_uniswap_v2_price, get_uniswap_v3_price  # Assuming this is the correct import
import json

class TestUniswapPriceRealData(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Setup Web3 connection to Ethereum mainnet (replace with your own Infura/Alchemy endpoint if needed)
        infura_url = 'https://rpc.mevblocker.io'
        cls.web3 = Web3(Web3.HTTPProvider(infura_url))
        
        if not cls.web3.is_connected():
            raise ConnectionError("Unable to connect to Ethereum mainnet.")
        
        # Set the real Uniswap V2 and V3 Factory addresses
        cls.UNISWAP_V2_FACTORY_ADDRESS = '0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f'  # Uniswap V2 Factory on Ethereum Mainnet
        cls.UNISWAP_V3_FACTORY_ADDRESS = '0x1F98431c8aD98523631AE4a59f267346ea31F984'  # Uniswap V3 Factory on Ethereum Mainnet
        cls.WETH_ADDRESS = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'  # WETH address on Ethereum Mainnet

        # Example token: USDC (you can replace this with any other token address)
        cls.USDC_ADDRESS = '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48'
        cls.TOKEN_DECIMALS = 6  # USDC has 6 decimals
        
        # Load the Uniswap V2 and V3 ABIs (you need to provide these in the test)
        with open('abis/IUniswapV2Factory.json') as file:
            cls.uniswap_v2_factory_abi = json.load(file)["abi"]
        
        with open('abis/IUniswapV2Pair.json') as file:
            cls.uniswap_v2_pair_abi = json.load(file)["abi"]
        
        with open('abis/IUniswapV3Factory.json') as file:
            cls.uniswap_v3_factory_abi = json.load(file)
        
        with open('abis/IUniswapV3Pool.json') as file:
            cls.uniswap_v3_pool_abi = json.load(file)

        # Create Uniswap factory contract instances
        cls.uniswap_v2_factory = cls.web3.eth.contract(address=cls.web3.to_checksum_address(cls.UNISWAP_V2_FACTORY_ADDRESS), abi=cls.uniswap_v2_factory_abi)
        cls.uniswap_v3_factory = cls.web3.eth.contract(address=cls.web3.to_checksum_address(cls.UNISWAP_V3_FACTORY_ADDRESS), abi=cls.uniswap_v3_factory_abi)

    def test_get_uniswap_v2_price(self):
        # Fetch price from Uniswap V2
        price, pair_address = get_uniswap_v2_price(self.web3, self.uniswap_v2_factory, self.USDC_ADDRESS, self.WETH_ADDRESS, self.TOKEN_DECIMALS, self.uniswap_v2_pair_abi)
        
        # Validate if we got a valid price and pair address
        self.assertIsNotNone(price, "Uniswap V2 price should not be None")
        self.assertIsNotNone(pair_address, "Uniswap V2 pair address should not be None")
        self.assertGreater(price, 0, "Uniswap V2 price should be greater than 0")
        print(f"Uniswap V2 price for USDC/WETH: {price} WETH")

    def test_get_uniswap_v3_price(self):
        # Fetch price from Uniswap V3
        price, pool_address = get_uniswap_v3_price(self.web3, self.uniswap_v3_factory, self.USDC_ADDRESS, self.WETH_ADDRESS, self.TOKEN_DECIMALS, self.uniswap_v3_pool_abi)
        
        # Validate if we got a valid price and pool address
        self.assertIsNotNone(price, "Uniswap V3 price should not be None")
        self.assertIsNotNone(pool_address, "Uniswap V3 pool address should not be None")
        self.assertGreater(price, 0, "Uniswap V3 price should be greater than 0")
        print(f"Uniswap V3 price for USDC/WETH: {price} WETH")


if __name__ == '__main__':
    unittest.main()
