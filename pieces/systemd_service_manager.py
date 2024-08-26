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
            # Using 'tail -f' to stream logs in real-time
            process = subprocess.Popen(['tail', '-f', log_file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            while True:
                line = process.stdout.readline()
                if line:
                    yield f"data: {line.decode('utf-8').strip()}\n\n"
                time.sleep(0.1)  # Slight delay to avoid excessive CPU usage
        except GeneratorExit:
            logging.info(f"Client disconnected from {service_name} logs stream.")
        except Exception as e:
            logging.error(f"Error in {service_name} logs streaming: {e}")
            yield f"data: Error in logs streaming: {e}\n\n"

    return generate()