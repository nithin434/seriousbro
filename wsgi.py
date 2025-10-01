#!/usr/bin/env python3
"""
WSGI entry point for Apache2
This file allows Apache to run the Flask application directly
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv('/home/clouduser/GEt/.env')
# Add the project directory to Python path
project_dir = '/home/clouduser/GEt'
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# Set environment variables
os.environ['FLASK_ENV'] = 'production'
os.environ['FLASK_APP'] = 'main.py'

# Add virtual environment to Python path
venv_path = '/home/clouduser/GEt/venv/lib/python3.11/site-packages'
if venv_path not in sys.path:
    sys.path.insert(0, venv_path)

# Set virtual environment variables
os.environ['VIRTUAL_ENV'] = '/home/clouduser/GEt/venv'

# Import the Flask app
from main import app

# WSGI application
application = app

if __name__ == "__main__":
    application.run()