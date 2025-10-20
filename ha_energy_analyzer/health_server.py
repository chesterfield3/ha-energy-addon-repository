#!/usr/bin/env python3
"""
Health check server for Home Assistant Add-on
Provides a simple HTTP endpoint for health monitoring
"""

import http.server
import socketserver
import threading
import json
from datetime import datetime

class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            health_data = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "service": "HA Energy Data Analyzer"
            }
            
            self.wfile.write(json.dumps(health_data).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass

def start_health_server(port=8080):
    """Start the health check server in a background thread"""
    handler = HealthCheckHandler
    
    try:
        with socketserver.TCPServer(("", port), handler) as httpd:
            print(f"Health check server started on port {port}")
            httpd.serve_forever()
    except Exception as e:
        print(f"Failed to start health server: {e}")

def start_health_server_thread(port=8080):
    """Start health server in background thread"""
    server_thread = threading.Thread(target=start_health_server, args=(port,), daemon=True)
    server_thread.start()
    return server_thread