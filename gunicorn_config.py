import os
import logging
from logging.handlers import TimedRotatingFileHandler

# Define the bind address and number of workers
bind = "0.0.0.0:8000"
workers = 2

# Log directories and files
log_dir = "logs/gunicorn"
accesslog = os.path.join(log_dir, "gunicorn_access.log")
errorlog = os.path.join(log_dir, "gunicorn_error.log")

# Ensure the log directory exists
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Setup logging
logger = logging.getLogger()

# Configure access log with daily rotation and keeping 30 days
access_handler = TimedRotatingFileHandler(accesslog, when="midnight", interval=1, backupCount=30)
access_handler.setLevel(logging.INFO)
access_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))

# Configure error log with daily rotation and keeping 30 days
error_handler = TimedRotatingFileHandler(errorlog, when="midnight", interval=1, backupCount=30)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Add handlers to the logger
logger.addHandler(access_handler)
logger.addHandler(error_handler)
