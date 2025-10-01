# SYNTEXA Setup Guide

## Quick Start (Recommended)

Since Apache2 is not fully installed, use the Python proxy:

```bash
# Start the application
./start.sh
```

This will:
- Start Flask app on port 5000
- Start proxy server on port 8080
- Handle requests for syntexa.app

## Access Your Application

- **Local**: http://localhost:8080
- **Domain**: http://syntexa.app:8080 (if DNS is configured)
- **IP**: http://YOUR_SERVER_IP:8080

## Files Created

- `proxy.py` - Reverse proxy server
- `start.sh` - Startup script
- `apache_config.conf` - Apache2 config (for future use)

## If You Get Apache2 Working Later

1. Install Apache2:
```bash
sudo apt update
sudo apt install apache2
```

2. Enable required modules:
```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod headers
```

3. Copy the config:
```bash
sudo cp apache_config.conf /etc/apache2/sites-available/syntexa.app.conf
sudo a2ensite syntexa.app.conf
sudo systemctl reload apache2
```

## Troubleshooting

- **Port 8080 in use**: Change `PROXY_PORT` in `proxy.py`
- **Flask not starting**: Check if all dependencies are installed
- **Permission denied**: Make sure `start.sh` is executable

## Current Setup

- ✅ Flask app on port 5000
- ✅ Proxy server on port 8080
- ✅ Domain routing for syntexa.app
- ✅ CORS headers
- ✅ Error handling
