import subprocess
import logging
import os

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