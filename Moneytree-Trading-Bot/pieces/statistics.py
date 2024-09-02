import json
import os
import logging
from datetime import datetime, timezone, timedelta
import shutil
import pytz

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Get the absolute path of the parent directory
parent_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

# Set the log directory and ensure it exists
log_directory = os.path.join(parent_directory, 'logs/statistics')
if not os.path.exists(log_directory):
    os.makedirs(log_directory)
    logging.info(f"Created log directory: {log_directory}")

# Set the log file path
log_file_path = os.path.join(log_directory, 'transaction_logs.json')

# Max number of backup logs
backup_count = 1095

# Assuming your local timezone is needed, adjust accordingly.
local_tz = pytz.timezone('Europe/Berlin')

# Function to rotate logs
def rotate_logs():
    # Convert the current time to the local timezone and then subtract one day to get the previous day
    now_local = datetime.now(local_tz)
    previous_day = now_local - timedelta(days=1)
    timestamp = previous_day.strftime("%Y%m%d")

    # Archive the current log file with a timestamp suffix
    if os.path.exists(log_file_path):
        archive_log_path = os.path.join(log_directory, f'transaction_logs_{timestamp}.json')
        shutil.move(log_file_path, archive_log_path)
        logging.info(f"Log file rotated to: {archive_log_path}")
    else:
        logging.info(f"No log file found to rotate at path: {log_file_path}")
        
    # Clean up old backups if they exceed the backup count
    log_files = [f for f in os.listdir(log_directory) if f.startswith('transaction_logs_') and f.endswith('.json')]
    log_files.sort(reverse=True)  # Sort by most recent

    if len(log_files) > backup_count:
        logging.info(f"Found {len(log_files)} log files, cleaning up old ones...")
    
    # Remove oldest logs if they exceed backup count
    for old_log in log_files[backup_count:]:
        old_log_path = os.path.join(log_directory, old_log)
        os.remove(old_log_path)
        logging.info(f"Deleted old log file: {old_log_path}")

# Function to check if a log rotation is needed (daily)
def is_rotation_needed():
    # Check if the current log exists and is from today in local time
    if os.path.exists(log_file_path):
        last_modified_time = datetime.fromtimestamp(os.path.getmtime(log_file_path), tz=timezone.utc)
        last_modified_time_local = last_modified_time.astimezone(local_tz)
        current_time_local = datetime.now(local_tz)

        logging.info(f"Last log file modification time (local): {last_modified_time_local}")
        logging.info(f"Current time (local): {current_time_local}")

        # Rotate if the log is from a previous day in local time
        if last_modified_time_local.date() < current_time_local.date():
            logging.info("Log rotation needed")
            return True
        else:
            logging.info("Log rotation not needed")
    else:
        logging.info("Log file does not exist, no rotation needed")
    return False

# Function to load logs from a file path
def load_logs(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as file:
                return json.load(file)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode JSON from {file_path}: {e}")
            return []
    return []

# Function to log or update transaction details to a JSON file
def log_transaction(data):
    logging.info("Starting transaction logging process...")

    # Rotate logs if needed
    if is_rotation_needed():
        rotate_logs()

    # Load the current log
    logs = load_logs(log_file_path)
    
    # Load the previous day's log
    previous_day = datetime.now(local_tz) - timedelta(days=1)
    previous_log_file = os.path.join(log_directory, f'transaction_logs_{previous_day.strftime("%Y%m%d")}.json')
    previous_logs = load_logs(previous_log_file)

    # Load the log from two days ago
    before_previous_day = datetime.now(local_tz) - timedelta(days=2)
    before_previous_log_file = os.path.join(log_directory, f'transaction_logs_{before_previous_day.strftime("%Y%m%d")}.json')
    before_previous_logs = load_logs(before_previous_log_file)

    # Combine logs in the order of current, previous, and before previous
    combined_logs = logs + previous_logs + before_previous_logs

    # Search for an existing entry with the same post_hash (tx_hash)
    existing_entry = None
    post_hash = data.get("post_hash")

    if post_hash:
        for log in combined_logs:
            if log.get("post_hash") == post_hash:
                existing_entry = log
                break

    if existing_entry:
        # Update the existing entry with new values
        logging.info(f"Updating existing log entry for post_hash: {post_hash}")
        existing_entry.update({
            "wallet_name": data.get("wallet_name", existing_entry["wallet_name"]),
            "token_symbol": data.get("token_symbol", existing_entry["token_symbol"]),
            "token_hash": data.get("token_hash", existing_entry["token_hash"]),
            "amount_of_eth": data.get("amount_of_eth", existing_entry["amount_of_eth"]),
            "buy": data.get("buy", existing_entry["buy"]),
            "buy_tx": data.get("buy_tx", existing_entry["buy_tx"]),
            "sell": data.get("sell", existing_entry["sell"]),
            "sell_tx": data.get("sell_tx", existing_entry["sell_tx"]),
            "fail": data.get("fail", existing_entry["fail"]),
            "profit_loss": data.get("profit_loss", existing_entry["profit_loss"])
        })

        # If the entry was in the previous or before previous logs, move it to the current log
        if existing_entry in previous_logs:
            previous_logs.remove(existing_entry)
            logs.append(existing_entry)
        elif existing_entry in before_previous_logs:
            before_previous_logs.remove(existing_entry)
            logs.append(existing_entry)
    else:
        # Append new log entry
        log_entry = {
            "time": data.get("time", datetime.now(timezone.utc).isoformat()),  # Current UTC time
            "post_hash": post_hash,  # Post hash (tx_hash)
            "wallet_name": data.get("wallet_name", "N/A"),  # Wallet name
            "token_symbol": data.get("token_symbol", "N/A"),  # Token symbol
            "token_hash": data.get("token_hash", "N/A"),
            "amount_of_eth": data.get("amount_of_eth", "N/A"),  # Amount of ETH
            "buy": data.get("buy", ""),  # Transaction status
            "buy_tx": data.get("buy_tx", ""), 
            "sell": data.get("sell", ""),
            "sell_tx": data.get("sell_tx", ""),
            "fail": data.get("fail", ""),  # Failure reason (if any)
            "profit_loss": data.get("profit_loss", "")  # Profit/loss (if success)
        }
        logs.append(log_entry)
        logging.info(f"Created new log entry for post_hash: {post_hash}")

    # Write the updated current log back to the file
    try:
        with open(log_file_path, 'w') as file:
            json.dump(logs, file, indent=4)
        logging.info(f"Logged transaction: {data}")
        
        # Optionally, update the previous and before previous day's logs if any entries were removed from them
        if previous_logs:
            with open(previous_log_file, 'w') as file:
                json.dump(previous_logs, file, indent=4)
            logging.info(f"Updated previous day's log: {previous_log_file}")
        
        if before_previous_logs:
            with open(before_previous_log_file, 'w') as file:
                json.dump(before_previous_logs, file, indent=4)
            logging.info(f"Updated before previous day's log: {before_previous_log_file}")

    except Exception as e:
        logging.error(f"Failed to write to log file: {e}")
