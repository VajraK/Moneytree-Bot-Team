# Moneytree Bot Team (MBT)

**Moneytree Bot Team (MBT)** is a comprehensive system designed to automate the tracking and trading of Ethereum-based transactions and tokens. It consists of three main components:

- **Moneytree Bot Console (MBC):** A Flask-based dashboard for managing configuration, viewing stats, and controlling the tracking and trading bots.
- **Moneytree Tracking Bot (MTB):** Continuously monitors Ethereum wallets for transactions and sends relevant alerts to Telegram.
- **Moneytree Trading Bot (MTdB):** Automatically executes buy and sell actions based on transaction data and market conditions.

## Features

- **Real-time Ethereum transaction tracking**
- **Automated trading based on price changes and custom rules**
- **Telegram notifications for important events**
- **Daily logs with backup rotation**
- **Rate limiting for secure user actions**
- **Session management with Redis**
- **Easy service management using SystemD**

## Table of Contents

- [Installation](#installation)
- [Setup](#setup)
- [Configuration](#configuration)
- [Running](#running)
- [SystemD Service Setup](#systemd-service-setup)
- [Redis Setup](#redis-setup)
- [Password and Secrets](#password-and-secrets)
- [Starting the Application](#starting-the-application)

---

## Installation

### Clone the Repository

```bash
git clone https://github.com/VajraK/Moneytree-Bot-Team
cd Moneytree-Bot-Team
mkdir logs
```

### Set up Virtual Environment and Install Dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Install Puppeteer (for web scraping)

```bash
npm install puppeteer puppeteer-extra puppeteer-extra-plugin-stealth
```

### Install required libraries for Puppeteer

```bash
sudo apt-get update
sudo apt-get install -y \
    libgbm1 \
    libasound2 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libxrandr2 \
    libgbm-dev \
    libnss3 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    fonts-liberation
```

### Copy Configuration Files

```bash
cp config.yaml.example config.yaml
cp .env_example .env
```

## Configuration

- Edit config.yaml to customize bot behavior. This file contains Ethereum settings, wallet addresses to monitor, Telegram bot settings, and trading parameters.
- Edit .env to set secret keys and environment-specific variables like APP_SECRET_KEY.

### Password Setup

Run the following script to generate a hashed password:

```bash
python pieces/generate_password_hash.py
```

Update config.yaml with the generated password hash.

## SystemD Service Setup

### MTB (Moneytree Tracking Bot)

Create a SystemD service file:

```bash
sudo nano /etc/systemd/system/mtb.service
```

Add the following configuration:

```bash
[Unit]
Description=Moneytree Tracking Bot (MTB)
After=network.target

[Service]
ExecStart=/usr/bin/python3 /path/to/Moneytree-Tracking-Bot/main.py
WorkingDirectory=/path/to/Moneytree-Tracking-Bot/
Restart=always
User=your_user
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
```

Reload SystemD and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable mtb.service
sudo systemctl start mtb.service
```

### MTdB (Moneytree Trading Bot)

Repeat the process for MTdB:

```bash
sudo nano /etc/systemd/system/mtdb.service
```

With the following configuration:

```bash
[Unit]
Description=Moneytree Trading Bot (MTdB)
After=network.target

[Service]
ExecStart=/usr/bin/python3 /path/to/Moneytree-Trading-Bot/main.py
WorkingDirectory=/path/to/Moneytree-Trading-Bot/
Restart=always
User=your_user
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
```

Start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable mtdb.service
sudo systemctl start mtdb.service
```

## Redis Setup

Install Redis:

```bash
sudo apt-get update
sudo apt-get install redis-server
```

Update Redis configuration:

```bash
Update Redis configuration:
```

Ensure the following line is set:

```bash
bind 127.0.0.1 ::1
```

Start Redis:

```bash
sudo service redis-server start
```

Install Python Redis package:

```bash
pip install redis
```

## Password and Secrets

- Set the password hash in config.yaml after generating it.
- Set APP_SECRET_KEY in .env for session management.

## Starting the Application

After setting up everything, start the Flask app (MBC):

```bash
gunicorn -c gunicorn_config.py app:app
```
