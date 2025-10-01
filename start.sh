#!/bin/bash

echo "🚀 Starting SYNTEXA..."
echo "======================"

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: main.py not found"
    exit 1
fi

# Create directories
mkdir -p static/roast_images
mkdir -p logs
mkdir -p uploads

# Set environment
export FLASK_ENV=production
export FLASK_APP=main.py

echo "🌐 Starting proxy server..."
echo "🔗 Domain: syntexa.app"
echo "🌍 Port: 8080"
echo "======================"

# Start the proxy (which starts Flask internally)
python3 proxy.py
