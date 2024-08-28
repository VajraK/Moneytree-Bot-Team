import json
import time
from flask import jsonify
from redis import Redis

# Set up Redis connection (you can adjust the host/port as needed)
redis_connection = Redis(host='localhost', port=6379)

# Function to read transaction logs and return JSON data
def get_transactions():
    try:
        with open('logs/statistics/transaction_logs.json', 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': 'Unable to read transaction logs.'}), 500

# Function to calculate the sum of profit_loss fields
def calculate_profit_loss(logger):
    while True:
        try:
            with open('logs/statistics/transaction_logs.json', 'r') as f:
                transactions = json.load(f)
                total_profit_loss = sum(
                    float(tx['profit_loss']) for tx in transactions if tx['profit_loss']
                )
                # Store the total profit/loss in Redis to share it between threads
                redis_connection.set('todays_profit_loss', total_profit_loss)
        except Exception as e:
            logger.error(f"Error calculating profit_loss: {e}")
            redis_connection.set('todays_profit_loss', 0)
        time.sleep(15)

# Route handler to fetch the current profit/loss from Redis
def get_todays_pl(logger):
    try:
        # Fetch the calculated profit/loss from Redis
        todays_pl = redis_connection.get('todays_profit_loss')
        if todays_pl is None:
            todays_pl = 0.0
        # Limit to 6 decimal places
        todays_pl = round(float(todays_pl), 6)
        return jsonify({"todaysPL": todays_pl})
    except Exception as e:
        logger.error(f"Error fetching today's P/L: {e}")
        return jsonify({"todaysPL": 0.0})
