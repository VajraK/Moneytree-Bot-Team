import subprocess
import logging
import os
import subprocess
import time
from collections import deque
from redis import Redis

# Get the absolute path of the parent directory
parent_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Initialize Redis connection
redis_conn = Redis(host='localhost', port=6379)  # Adjust Redis host/port as needed

def log_to_redis(service_name, log_line):
    # Push logs into Redis lists
    redis_conn.rpush(f'logs:{service_name}', log_line)

def get_logs_from_redis(service_name, limit=25):
    # Get the last `limit` number of logs from Redis
    return redis_conn.lrange(f'logs:{service_name}', -limit, -1)

def add_log(service_name, log_message):
    log_line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {log_message}"
    log_to_redis(service_name, log_line)
    redis_conn.publish(f'logs_channel:{service_name}', log_line)  # Publish log to the Redis pub/sub channel

def start_service(service_name):
    try:
        subprocess.run(['sudo', 'systemctl', 'start', f'{service_name}.service'], check=True)
        message = f"{service_name} service started successfully."
        logging.info(message)
        add_log(service_name, message)  # Push log to Redis
        return True, message
    except subprocess.CalledProcessError as e:
        message = f"Error starting {service_name} service: {e}"
        logging.error(message)
        add_log(service_name, message)  # Push log to Redis
        return False, message

def stop_service(service_name):
    try:
        subprocess.run(['sudo', 'systemctl', 'stop', f'{service_name}.service'], check=True)
        message = f"{service_name} service stopped successfully."
        logging.info(message)
        add_log(service_name, message)  # Push log to Redis
        return True, message
    except subprocess.CalledProcessError as e:
        message = f"Error stopping {service_name} service: {e}"
        logging.error(message)
        add_log(service_name, message)  # Push log to Redis
        return False, message

def restart_service(service_name):
    try:
        subprocess.run(['sudo', 'systemctl', 'restart', f'{service_name}.service'], check=True)
        message = f"{service_name} service restarted successfully."
        logging.info(message)
        add_log(service_name, message)  # Push log to Redis
        return True, message
    except subprocess.CalledProcessError as e:
        message = f"Error restarting {service_name} service: {e}"
        logging.error(message)
        add_log(service_name, message)  # Push log to Redis
        return False, message

def get_service_status(service_name):
    try:
        result = subprocess.run(['systemctl', 'is-active', f'{service_name}.service'], stdout=subprocess.PIPE)
        status = result.stdout.decode().strip()
        if status == 'active':
            return 'running'
        return 'stopped'
    except subprocess.CalledProcessError as e:
        message = f"Error checking {service_name} service status: {e}"
        logging.error(message)
        add_log(service_name, message)  # Push log to Redis
        return 'error'

def stream_logs(service_name):
    # Determine the log file path based on the service name
    if service_name == "mtb":
        log_file_path = os.path.join(parent_directory, 'logs', 'mtb', 'mtb.log')
    elif service_name == "mtdb":
        log_file_path = os.path.join(parent_directory, 'logs', 'mtdb', 'mtdb.log')
    else:
        log_file_path = os.path.join(parent_directory, 'logs', f'{service_name}.log')  # Fallback for other logs

    if not os.path.exists(log_file_path):
        return "Log file does not exist."

    def generate():
        try:
            # Use 'tail -f' to stream the log file
            process = subprocess.Popen(['tail', '-f', log_file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            while True:
                # Read new lines from the tail process
                line = process.stdout.readline()
                if line:
                    yield f"data: {line.decode('utf-8').strip()}\n\n"
                else:
                    # Keep yielding if no new line is available
                    yield ":\n\n"  # Send heartbeat to keep connection alive

        except GeneratorExit:
            logging.info(f"Client disconnected from {service_name} logs stream.")
            process.terminate()  # Terminate the tail process if client disconnects
        except Exception as e:
            logging.error(f"Error in {service_name} logs streaming: {e}")
            yield f"data: Error in logs streaming: {e}\n\n"

    return generate()