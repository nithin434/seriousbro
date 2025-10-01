#!/usr/bin/env python3
"""
Minimal Reverse Proxy for syntexa.app
Forwards requests to Flask app on port 5000
"""

import socket
import threading
import time
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error

# Configuration
FLASK_HOST = 'localhost'
FLASK_PORT = 5000
PROXY_HOST = '0.0.0.0'
PROXY_PORT = 8080  # Use 8080 since we don't have root access for port 80

class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._proxy_request('GET')
    
    def do_POST(self):
        self._proxy_request('POST')
    
    def do_PUT(self):
        self._proxy_request('PUT')
    
    def do_DELETE(self):
        self._proxy_request('DELETE')
    
    def do_OPTIONS(self):
        self._proxy_request('OPTIONS')
    
    def _proxy_request(self, method):
        try:
            # Get request data
            path = self.path
            headers = dict(self.headers)
            
            # Target URL
            target_url = f"http://{FLASK_HOST}:{FLASK_PORT}{path}"
            
            print(f"[{time.strftime('%H:%M:%S')}] {method} {path}")
            
            # Create request
            req = urllib.request.Request(target_url, method=method)
            
            # Copy headers
            for header, value in headers.items():
                if header.lower() != 'host':
                    req.add_header(header, value)
            
            # Handle POST data
            if method in ['POST', 'PUT']:
                content_length = int(headers.get('Content-Length', 0))
                if content_length > 0:
                    post_data = self.rfile.read(content_length)
                    req.data = post_data
            
            # Forward request
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    # Send response
                    self.send_response(response.status)
                    
                    # Copy headers
                    for header, value in response.getheaders():
                        if header.lower() not in ['transfer-encoding']:
                            self.send_header(header, value)
                    
                    # Add CORS
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
                    self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
                    
                    self.end_headers()
                    self.wfile.write(response.read())
                    
            except urllib.error.HTTPError as e:
                self.send_response(e.code)
                for header, value in e.headers.items():
                    self.send_header(header, value)
                self.end_headers()
                self.wfile.write(e.read())
                
            except urllib.error.URLError as e:
                print(f"Error: {e}")
                self.send_error(502, "Bad Gateway")
                
        except Exception as e:
            print(f"Proxy error: {e}")
            self.send_error(500, "Internal Server Error")
    
    def log_message(self, format, *args):
        # Minimal logging
        pass

def start_flask():
    """Start Flask app in background"""
    def run():
        try:
            os.chdir('/home/clouduser/GEt')
            os.environ['FLASK_ENV'] = 'production'
            os.environ['FLASK_APP'] = 'main.py'
            
            from main import app
            print("🚀 Flask app starting on port 5000...")
            app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
        except Exception as e:
            print(f"❌ Flask error: {e}")
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread

def check_flask():
    """Check if Flask is running"""
    try:
        response = urllib.request.urlopen(f'http://{FLASK_HOST}:{FLASK_PORT}/health', timeout=5)
        return response.getcode() == 200
    except:
        return False

def main():
    print("🌐 SYNTEXA Proxy Server")
    print("=" * 30)
    print(f"Domain: syntexa.app")
    print(f"Proxy: {PROXY_HOST}:{PROXY_PORT}")
    print(f"Flask: {FLASK_HOST}:{FLASK_PORT}")
    print("=" * 30)
    
    # Start Flask
    print("🔄 Starting Flask app...")
    flask_thread = start_flask()
    
    # Wait for Flask
    print("⏳ Waiting for Flask...")
    for i in range(30):
        if check_flask():
            print("✅ Flask ready!")
            break
        time.sleep(1)
        if i % 5 == 0:
            print(f"⏳ Still waiting... ({i}/30)")
    else:
        print("❌ Flask failed to start")
        sys.exit(1)
    
    # Start proxy
    try:
        print(f"🌐 Starting proxy on port {PROXY_PORT}...")
        server = HTTPServer((PROXY_HOST, PROXY_PORT), ProxyHandler)
        
        print("✅ Proxy running!")
        print(f"🔗 Access: http://syntexa.app:{PROXY_PORT}")
        print("🔄 Press Ctrl+C to stop")
        
        server.serve_forever()
        
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
        server.shutdown()
    except Exception as e:
        print(f"❌ Proxy error: {e}")

if __name__ == "__main__":
    main()
