import subprocess
import logging
import os
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
        logging.error(f"Log file for {service_name} does not exist at {log_file_path}.")
        return "Log file does not exist."

    def generate():
        try:
            # First, send the last 25 lines (or fewer if the log file is small)
            with open(log_file_path, "r") as f:
                last_lines = deque(f, maxlen=25)  # Read the last 25 lines
                for line in last_lines:
                    yield f"data: {line.strip()}\n\n"

            # Now, seek to the end of the file and start streaming new logs
            with open(log_file_path, "r") as f:
                f.seek(0, os.SEEK_END)  # Go to the end of the file
                last_heartbeat = time.time()
                while True:
                    line = f.readline()
                    if line:
                        yield f"data: {line.strip()}\n\n"
                    else:
                        # Send a "heartbeat" comment every 15 seconds to keep the connection alive
                        current_time = time.time()
                        if current_time - last_heartbeat > 15:
                            yield ":\n\n"  # This is a comment (heartbeat) in SSE; it won't be displayed to the client
                            last_heartbeat = current_time
                        time.sleep(0.5)  # Sleep briefly to avoid busy-waiting

        except GeneratorExit:
            logging.info(f"Client disconnected from {service_name} logs stream.")
        except Exception as e:
            logging.error(f"Error in {service_name} logs streaming: {e}")
            yield f"data: Error in logs streaming: {e}\n\n"

    return generate()
