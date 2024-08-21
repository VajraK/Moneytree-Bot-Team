import logging
import yaml
from datetime import datetime, timedelta, timezone
import os

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

# Load environment variables
NO_CHANGE_THRESHOLD_PERCENT = config['NO_CHANGE_THRESHOLD_PERCENT']
NO_CHANGE_TIME_MINUTES = config['NO_CHANGE_TIME_MINUTES']

def check_no_change_threshold(start_time, price_history, monitoring_id, symbol, token_amount):
    current_time = datetime.now(timezone.utc)
    intervals_passed = (current_time - start_time) // timedelta(minutes=NO_CHANGE_TIME_MINUTES)
    threshold_percent = NO_CHANGE_THRESHOLD_PERCENT * 100  # Convert to percentage for logging

    if intervals_passed > 0:
        for interval in range(intervals_passed):
            interval_start_time = start_time + timedelta(minutes=interval * NO_CHANGE_TIME_MINUTES)
            interval_end_time = interval_start_time + timedelta(minutes=NO_CHANGE_TIME_MINUTES)

            # Filter the price history to only include prices within the current interval
            interval_prices = [price for timestamp, price in price_history if interval_start_time <= timestamp < interval_end_time]

            if not interval_prices:
                continue

            min_price = min(interval_prices)
            max_price = max(interval_prices)
            initial_price = interval_prices[0]
            price_increase = (max_price - initial_price) / initial_price
            price_decrease = (initial_price - min_price) / initial_price

            if abs(price_increase) < NO_CHANGE_THRESHOLD_PERCENT and abs(price_decrease) < NO_CHANGE_THRESHOLD_PERCENT:
                logging.info(f"Monitoring {monitoring_id} — No significant price change — {threshold_percent:.2f}%. — detected in a {NO_CHANGE_TIME_MINUTES} minutes interval. Selling the token.")
                return True, token_amount, f'Price did not change significantly — {threshold_percent:.2f}%. — in a {NO_CHANGE_TIME_MINUTES} minutes interval.', start_time
            else:
                logging.info(f"Monitoring {monitoring_id} — Significant price — {threshold_percent:.2f}%. — in a {NO_CHANGE_TIME_MINUTES} minutes interval. Continuing monitoring.")
                return False, None, None, interval_end_time  # Return the updated start time

    return False, None, None, start_time  # Return the original start time if no intervals passed