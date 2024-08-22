import subprocess
import logging
import os
import time
from collections import deque

# Get the absolute path of the parent directory
parent_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def start_service(service_name):
    try:
        subprocess.run(['sudo', 'systemctl', 'start', f'{service_name}.service'], check=True)
        logging.info(f"{service_name} service started successfully.")
        return True, f"{service_name} service started successfully."
    except subprocess.CalledProcessError as e:
        logging.error(f"Error starting {service_name} service: {e}")
        return False, f"Error starting {service_name} service: {e}"

def stop_service(service_name):
    try:
        subprocess.run(['sudo', 'systemctl', 'stop', f'{service_name}.service'], check=True)
        logging.info(f"{service_name} service stopped successfully.")
        return True, f"{service_name} service stopped successfully."
    except subprocess.CalledProcessError as e:
        logging.error(f"Error stopping {service_name} service: {e}")
        return False, f"Error stopping {service_name} service: {e}"

def restart_service(service_name):
    try:
        subprocess.run(['sudo', 'systemctl', 'restart', f'{service_name}.service'], check=True)
        logging.info(f"{service_name} service restarted successfully.")
        return True, f"{service_name} service restarted successfully."
    except subprocess.CalledProcessError as e:
        logging.error(f"Error restarting {service_name} service: {e}")
        return False, f"Error restarting {service_name} service: {e}"

def get_service_status(service_name):
    try:
        result = subprocess.run(['systemctl', 'is-active', f'{service_name}.service'], stdout=subprocess.PIPE)
        status = result.stdout.decode().strip()
        if status == 'active':
            return 'running'
        return 'stopped'
    except subprocess.CalledProcessError as e:
        logging.error(f"Error checking {service_name} service status: {e}")
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
                while True:
                    line = f.readline()
                    if line:
                        yield f"data: {line.strip()}\n\n"
                    else:
                        time.sleep(0.5)  # Sleep briefly to avoid busy-waiting
        except GeneratorExit:
            logging.info(f"Client disconnected from {service_name} logs stream.")
        except Exception as e:
            logging.error(f"Error in {service_name} logs streaming: {e}")
            yield f"data: Error in logs streaming: {e}\n\n"

    return generate()