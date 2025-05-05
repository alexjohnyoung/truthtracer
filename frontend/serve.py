"""
Simple HTTP Server for TruthTracer Frontend

This script starts a simple HTTP server to serve the TruthTracer frontend.
"""

import http.server
import socketserver
import webbrowser
from pathlib import Path
import argparse
from os import chdir 

def run_server(port=8080, open_browser=True):
    """Run a simple HTTP server for the frontend"""
    
    # Get the directory containing this script
    current_dir = Path(__file__).parent.absolute()
    
    # Change to that directory
    chdir(current_dir)
    
    # Create a handler that serves files from the current directory
    handler = http.server.SimpleHTTPRequestHandler
    
    # Create TCP server
    with socketserver.TCPServer(("", port), handler) as httpd:
        url = f"http://localhost:{port}"
        print(f"Serving TruthTracer frontend at {url}")
        
        # Open browser if requested
        if open_browser:
            webbrowser.open(url)
        
        print("Press Ctrl+C to stop the server")
        
        # Start the server
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start a simple HTTP server for TruthTracer frontend")
    parser.add_argument(
        "-p", "--port", 
        type=int, 
        default=8080, 
        help="Port to run the server on (default: 8080)"
    )
    parser.add_argument(
        "--no-browser", 
        action="store_true", 
        help="Don't open a browser automatically"
    )
    
    args = parser.parse_args()
    
    run_server(port=args.port, open_browser=not args.no_browser) 