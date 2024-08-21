import subprocess
import os
import time
import logging

def scrape_dexanalyzer(token_hash, save_html=True, max_attempts=15):
    logs_directory = 'logs/dexanalyzer'
    file_path = os.path.join(logs_directory, f'{token_hash}.html')

    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        try:
            # Run the Puppeteer script
            result = subprocess.run(['node', 'pieces/dexanalyzer_scraper.js', token_hash], capture_output=True, text=True, check=True)
            content = result.stdout

            # Check if the content contains the "Loading" message
            if "<h1>Loading" in content:
                logging.info(f"Attempt {attempt}: Page is still loading. Retrying...")
                time.sleep(2)  # Wait for 2 seconds before retrying
                continue

            # Save the HTML content if the option is enabled
            if save_html:
                os.makedirs(logs_directory, exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(content)
                logging.info(f"HTML content saved to {file_path}")

            # Perform the scam checks based on the three filters
            return check_for_scam(content)

        except subprocess.CalledProcessError as e:
            logging.error(f"An error occurred: {e}")
            return False  # Assume no scam detected on error
    
    logging.error("Maximum attempts reached. The page might still be loading.")
    return False  # Return False if loading persists after max attempts

def check_for_scam(content):
    # 1. MUST NOT CONTAIN 'HIGH</b></td><td>MOST LIKELY SCAM'
    scam_expression = 'HIGH</b></td><td>MOST LIKELY SCAM'
    if scam_expression in content:
        logging.warning("Scam detected: Contains 'HIGH</b></td><td>MOST LIKELY SCAM'")
        return True  # Scam detected
    
    # 2. MUST CONTAIN '***RENOUNCED***'
    renounced_expression = '***RENOUNCED***'
    if renounced_expression not in content:
        logging.warning("Scam detected: Does not contain '***RENOUNCED***'")
        return True  # Scam detected
    
    # 3. MUST CONTAIN at least one of these: 'Liquidity burned', 'locked for'
    liquidity_burned = 'Liquidity burned'
    locked_for = 'locked for'
    if liquidity_burned not in content and locked_for not in content:
        logging.warning("Scam detected: Does not contain 'Liquidity burned' or 'locked for'")
        return True  # Scam detected

    # If none of the scam conditions are met, return False
    logging.info("No scam detected.")
    return False  # No scam detected
