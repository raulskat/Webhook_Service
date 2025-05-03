from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import hmac
import hashlib
import logging
import socket
import sys
import traceback

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            logger.info(f"\n=== Received request on path: {self.path} ===")
            logger.info(f"Client Address: {self.client_address}")
            
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            # Print received data
            logger.info("\n=== Received Webhook ===")
            logger.info(f"Headers: {dict(self.headers)}")
            logger.info(f"Body: {body.decode()}")
            
            # Verify signature if present
            signature = self.headers.get('X-Hook-Signature')
            if signature:
                # Get the secret from the subscription
                secret = "supersecret"  # This should match the subscription secret
                expected_sig = hmac.new(
                    secret.encode(),
                    body,
                    hashlib.sha256
                ).hexdigest()
                
                if hmac.compare_digest(signature, expected_sig):
                    logger.info("Signature verified successfully!")
                else:
                    logger.error("Invalid signature!")
                    logger.error(f"Expected: {expected_sig}")
                    logger.error(f"Received: {signature}")
            
            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = json.dumps({"status": "received"}).encode()
            self.wfile.write(response)
            logger.info("Response sent successfully")
            
        except Exception as e:
            logger.error(f"Error handling request: {str(e)}")
            logger.error(traceback.format_exc())
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_GET(self):
        """Handle GET requests for health checks and other endpoints"""
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy"}).encode())
        else:
            self.send_response(501)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Method not implemented"}).encode())

def run(server_class=HTTPServer, handler_class=WebhookHandler, port=9000):
    try:
        server_address = ('0.0.0.0', port)
        httpd = server_class(server_address, handler_class)
        hostname = socket.gethostname()
        logger.info(f"Starting test server on port {port}...")
        logger.info(f"Server is listening on {hostname}:{port}")
        logger.info(f"Server local IP: {socket.gethostbyname(hostname)}")
        httpd.serve_forever()
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    run() 