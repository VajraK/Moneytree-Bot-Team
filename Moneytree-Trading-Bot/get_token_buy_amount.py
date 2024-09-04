import time
import logging
from web3 import Web3
from web3.exceptions import TransactionNotFound

class TokenAnalyzer:
    def __init__(self, infura_url):
        self.web3 = Web3(Web3.HTTPProvider(infura_url))

    def get_token_amount(self, tx_hash, token_contract_address=None, max_retries=90, delay=2):
        retries = 0
        while retries < max_retries:
            try:
                # Attempt to get the transaction receipt
                tx_receipt = self.web3.eth.get_transaction_receipt(tx_hash)
                
                # Log successful retrieval of the transaction receipt
                logging.info(f"Transaction receipt found on try {retries + 1}.")
                
                # Check for token transfer events (Transfer method signature: 0xddf252ad)
                token_transfers = [log for log in tx_receipt.logs if log['topics'][0].hex() == Web3.keccak(text="Transfer(address,address,uint256)").hex()]
                
                if not token_transfers:
                    logging.warning(f"No token transfers found in transaction {tx_hash}.")
                    return "No token transfers found in this transaction"
                
                logging.info(f"Token transfers found: {len(token_transfers)} transfers.")
                
                total_token_amount = 0
                
                # Loop through all transfers and sum the amount for the specified token
                for transfer in token_transfers:
                    contract_address = transfer['address']
                    
                    if token_contract_address and self.web3.to_checksum_address(contract_address) != self.web3.to_checksum_address(token_contract_address):
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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Example usage
if __name__ == "__main__":
    infura_url = "https://rpc.mevblocker.io"
    tx_hash = "0x2d1dfb0d579e2365c011352b6655431f29ace627f378e77bfc0d83e0319cede3"
    token_contract_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"  # Example: WETH contract address
    
    analyzer = TokenAnalyzer(infura_url)
    result = analyzer.get_token_amount(tx_hash, token_contract_address)
    print(result)
