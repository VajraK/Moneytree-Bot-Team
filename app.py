from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, jsonify
import yaml
import json
import os
from datetime import timedelta
from functools import wraps
from dotenv import load_dotenv
import logging
from logging.handlers import TimedRotatingFileHandler
from pieces.systemd_service_manager import start_service, stop_service, restart_service, get_service_status, stream_logs
import bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from redis import Redis
from flask_session import Session 

# Define the log directory and file
log_dir = "logs/app"
log_file = os.path.join(log_dir, "app.log")

# Ensure the log directory exists
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Setup the logger
logger = logging.getLogger()

# Remove any existing handlers if the app restarts
if logger.hasHandlers():
    logger.handlers.clear()

# Create a rotating log handler with daily rotation and keeping 30 days of logs
handler = TimedRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=30)
handler.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Add handler to the logger
logger.addHandler(handler)

# Optionally set the basic logging configuration for debugging to stdout
logging.basicConfig(level=logging.DEBUG)

# Importing helper functions from pieces/config.py
from pieces.config import (
    update_ethereum_settings,
    update_wallet_config,
    update_trading_parameters,
    update_telegram_settings,
    update_feature_toggles,
    update_addresses_to_monitor
)

app = Flask(__name__)

# Load environment variables
load_dotenv()

CONFIG_FILE_PATH = 'config.yaml'
app.secret_key = os.getenv('APP_SECRET_KEY')

# Set up Redis connection
redis_connection = Redis(host='localhost', port=6379)  # Adjust host/port if needed

# Set up Flask-Limiter with Redis as the storage backend
limiter = Limiter(
    get_remote_address,  # Use client IP for rate limiting
    app=app,  # Attach Limiter to the Flask app
    storage_uri="redis://localhost:6379",  # Use Redis as the storage backend
    default_limits=["200 per day", "50 per hour"]  # Default rate limits
)

# Flask-Session configuration
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis_connection
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)
app.config['SESSION_USE_SIGNER'] = True  # Sign session cookies for extra security
app.config['SESSION_KEY_PREFIX'] = 'session:'  # Optional: Add a prefix to session keys in Redis

# Initialize the Flask-Session extension
Session(app)

class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True

def yaml_dump(data, stream=None, **kwargs):
    return yaml.dump(data, stream, Dumper=NoAliasDumper, sort_keys=False, **kwargs)

def load_config():
    with open(CONFIG_FILE_PATH, 'r') as file:
        return yaml.safe_load(file)

def save_config(config):
    with open(CONFIG_FILE_PATH, 'w') as file:
        yaml_dump(config, file, allow_unicode=True)

# Check the password against the hashed version
def check_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('You need to login first.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")  # Limit to 5 login attempts per minute per IP address
def login():
    config = load_config()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Validate username and password using bcrypt
        if username == config['USERNAME'] and check_password(password, config['PASSWORD']):
            session['logged_in'] = True
            flash('You were successfully logged in.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid Credentials. Please try again.', 'danger')
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout():
    try:
        if 'logged_in' in session:
            session.clear()  # This clears all the session data
            flash('You were successfully logged out.', 'success')
        return redirect(url_for('login'))
    except Exception as e:
        print(f"Error during logout: {e}")
        return "Internal Server Error", 500

@app.route('/')
@login_required
def index():
    config = load_config()
    return render_template('index.html', config=config)

@app.route('/update', methods=['POST'])
@login_required
@limiter.exempt
def update():
    config = load_config()
    
    # Update different sections using modularized functions
    update_ethereum_settings(config, request.form)
    update_wallet_config(config, request.form)
    update_trading_parameters(config, request.form)
    update_telegram_settings(config, request.form)
    update_feature_toggles(config, request.form)
    update_addresses_to_monitor(config, request.form)
    
    # Save the updated config back to the YAML file
    save_config(config)
    
    return redirect(url_for('index'))

@app.route('/get_transactions')
@login_required
@limiter.exempt
def get_transactions():
    # Read the transaction_logs.json file
    try:
        with open('logs/statistics/transaction_logs.json') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': 'Unable to read transaction logs.'}), 500

@app.route('/start_mtb', methods=['POST'])
@login_required
def start_mtb():
    success, message = start_service('mtb')
    flash(message, 'success' if success else 'danger')
    return '', 204


@app.route('/stop_mtb', methods=['POST'])
@login_required
def stop_mtb():
    success, message = stop_service('mtb')
    flash(message, 'success' if success else 'danger')
    return '', 204

@app.route('/restart_mtb', methods=['POST'])
@login_required
def restart_mtb():
    success, message = restart_service('mtb')
    flash(message, 'success' if success else 'danger')
    return '', 204

@app.route('/mtb_status', methods=['GET'])
@login_required
@limiter.exempt
def mtb_status():
    status = get_service_status('mtb')
    return {'status': status}

@app.route('/start_mtdb', methods=['POST'])
@login_required
def start_mtdb():
    success, message = start_service('mtdb')
    flash(message, 'success' if success else 'danger')
    return '', 204

@app.route('/stop_mtdb', methods=['POST'])
@login_required
def stop_mtdb():
    success, message = stop_service('mtdb')
    flash(message, 'success' if success else 'danger')
    return '', 204

@app.route('/restart_mtdb', methods=['POST'])
@login_required
def restart_mtdb():
    success, message = restart_service('mtdb')
    flash(message, 'success' if success else 'danger')
    return '', 204

@app.route('/mtdb_status', methods=['GET'])
@login_required
@limiter.exempt
def mtdb_status():
    status = get_service_status('mtdb')
    return {'status': status}

@app.route('/logs/<service_name>')
@login_required
@limiter.exempt
def logs(service_name):
    if service_name in ['mtb', 'mtdb']:
        return Response(stream_logs(service_name), mimetype='text/event-stream')
    else:
        return "Invalid service name", 400