import sys
import os
import asyncio
import json
from http.server import BaseHTTPRequestHandler

# Path ঠিক করা
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Server is online!")

    def do_POST(self):
        try:
            from bot import app, initialize_app, WEBHOOK_SECRET
            from telegram import Update

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
            self.wfile.write(str(e).encode('utf-8'))
