import sys
import os
import asyncio
import json
from http.server import BaseHTTPRequestHandler
from telegram import Update

# Root directory-কে Python path-এ যুক্ত করা (সঠিকভাবে ২ ধাপ ওপরে যাওয়া হচ্ছে)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# আপনার bot.py থেকে প্রয়োজনীয় জিনিসপত্র ইম্পোর্ট
from bot import app, initialize_app, WEBHOOK_SECRET

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            # Vercel Webhook secret verification (যদি ব্যবহার করেন)
            secret_header = self.headers.get('X-Telegram-Bot-Api-Secret-Token')
            if WEBHOOK_SECRET and secret_header != WEBHOOK_SECRET:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Unauthorized")
                return

            json_data = json.loads(post_data.decode('utf-8'))
            
            # Asyncio loop হ্যান্ডেল করে টেলিগ্রাম আপডেট পাস করা
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # বট ইনিশিয়ালাইজ না হয়ে থাকলে করা
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

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")
