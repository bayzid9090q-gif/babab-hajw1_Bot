import sys
import os
import asyncio
import json
from http.server import BaseHTTPRequestHandler
from telegram import Update

# Root directory path ঠিকভাবে যুক্ত করা
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

# Safe Import handling
try:
    from bot import app, initialize_app, WEBHOOK_SECRET
except Exception as e:
    app = None
    initialize_app = None
    WEBHOOK_SECRET = None
    import_error = str(e)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if 'import_error' in globals() and import_error:
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Import Error: {import_error}".encode('utf-8'))
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            secret_header = self.headers.get('X-Telegram-Bot-Api-Secret-Token')
            if WEBHOOK_SECRET and secret_header != WEBHOOK_SECRET:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Unauthorized")
                return

            json_data = json.loads(post_data.decode('utf-8'))
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            loop.run_until_complete(initialize_app())
            
            update = Update.de_json(json_data, app.bot)
            loop.run_until_complete(app.process_update(update))
            
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"OK")
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Runtime Error: {str(e)}".encode('utf-8'))

    def do_GET(self):
        if 'import_error' in globals() and import_error:
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Import Error: {import_error}".encode('utf-8'))
            return

        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")
