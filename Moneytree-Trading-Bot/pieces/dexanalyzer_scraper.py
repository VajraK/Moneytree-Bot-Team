import subprocess
import os
import time
import logging
import yaml

def scrape_dexanalyzer(token_hash, save_html=True, max_attempts=15):
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

    # Load scam check configuration
    ENABLE_HIGH_MOST_LIKELY_SCAM_CHECK = config['ENABLE_HIGH_MOST_LIKELY_SCAM_CHECK']
    ENABLE_RENOUNCED_CHECK = config['ENABLE_RENOUNCED_CHECK']
    ENABLE_LIQUIDITY_CHECK = config['ENABLE_LIQUIDITY_CHECK']

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
                logging.info(f"[Anti-Scam] Attempt {attempt}: Page is still loading. Retrying...")
                time.sleep(2)  # Wait for 2 seconds before retrying
                continue

            # Save the HTML content if the option is enabled
            if save_html:
                os.makedirs(logs_directory, exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(content)
                logging.info(f"HTML content saved to {file_path}")

            # Perform the scam checks based on the configuration
            scam_result, reason = check_for_scam(content, ENABLE_HIGH_MOST_LIKELY_SCAM_CHECK, ENABLE_RENOUNCED_CHECK, ENABLE_LIQUIDITY_CHECK)
            if scam_result:
                logging.warning(f"! {reason}")
            return scam_result, reason

        except subprocess.CalledProcessError as e:
            logging.error(f"An error occurred: {e}")
            return False, "Script error"  # Return error for subprocess failure
    
    logging.error("Maximum attempts reached. The page might still be loading.")
    return False, "Page loading timeout"  # Return timeout error if loading persists after max attempts

def check_for_scam(content, enable_high_most_likely_scam_check, enable_renounced_check, enable_liquidity_check):
    # 1. MUST NOT CONTAIN 'HIGH</b></td><td>MOST LIKELY SCAM'
    if enable_high_most_likely_scam_check:
        scam_expression = 'HIGH</b></td><td>MOST LIKELY SCAM'
        if scam_expression in content:
            reason = "Scam detected: HIGH Priority'"
            return True, reason  # Scam detected
    
    # 2. MUST CONTAIN '***RENOUNCED***'
    if enable_renounced_check:
        renounced_expression = '***RENOUNCED***'
        if renounced_expression not in content:
            reason = "Scam detected: Not Renounced"
            return True, reason  # Scam detected
    
    # 3. MUST CONTAIN at least one of these: 'Liquidity burned', 'locked for'
    if enable_liquidity_check:
        liquidity_burned = 'Liquidity burned'
        locked_for = 'locked for'
        if liquidity_burned not in content and locked_for not in content:
            reason = "Scam detected: Liquidity Not Burned Nor Locked"
            return True, reason  # Scam detected

    # If none of the scam conditions are met, return False
    return False, ""  # No scam detected
