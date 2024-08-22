import subprocess
import logging
import os
import time

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
    if service_name == 'mtb':
        log_file_path = os.path.join(parent_directory, 'logs', 'mtb', 'mtb.log')
    elif service_name == 'mtdb':
        log_file_path = os.path.join(parent_directory, 'logs', 'mtdb', 'mtdb.log')
    else:
        logging.error(f"Invalid service name: {service_name}")
        return "Invalid service name."

    if not os.path.exists(log_file_path):
        logging.error(f"Log file for {service_name} does not exist at {log_file_path}.")
        return "Log file does not exist."

    def generate():
        logging.info(f"Starting to stream logs for {service_name} from {log_file_path}")
        try:
            with open(log_file_path) as f:
                # Read and send the entire content of the log file from the beginning
                for line in f:
                    logging.info(f"Sending log line: {line.strip()}")  # Debug logging
                    yield f"data: {line}\n\n"
                
                # Now, seek the end of the file to continue streaming new logs
                f.seek(0, os.SEEK_END)
                while True:
                    line = f.readline()
                    if line:
                        logging.info(f"Sending new log line: {line.strip()}")  # Debug logging
                        yield f"data: {line}\n\n"
                    else:
                        time.sleep(1)  # Sleep briefly to avoid busy-waiting
        except GeneratorExit:
            logging.info(f"Client disconnected from {service_name} logs stream.")
        except Exception as e:
            logging.error(f"Error in {service_name} logs streaming: {e}")
            yield f"data: Error in logs streaming: {e}\n\n"
    
    return generate()
