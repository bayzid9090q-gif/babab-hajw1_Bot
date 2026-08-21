import asyncio
import json
import os
from http.server import BaseHTTPRequestHandler

from telegram import Update

from bot import app, initialize_app, WEBHOOK_SECRET


def run(coro):
    """Run one async PTB operation inside the Vercel invocation."""
    return asyncio.run(coro)


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="text/plain; charset=utf-8"):
        body_bytes = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def do_GET(self):
        token = os.environ.get("BOT_TOKEN")
        if not token:
            self._send(500, "Error: BOT_TOKEN is missing in Vercel Environment Variables!")
            return

        path_only = self.path.split("?", 1)[0].rstrip("/")
        if path_only in ["/api", "", "/"]:
            if "setup=1" in self.path:
                webhook_url = os.environ.get("WEBHOOK_URL")
                if not webhook_url:
                    host = self.headers.get("Host", "")
                    if host:
                        webhook_url = f"https://{host}/api"

                if not webhook_url:
                    self._send(
                        500,
                        "WEBHOOK_URL environment variable is missing."
                    )
                    return

                try:
                    run(initialize_app())
                    secret = os.environ.get("WEBHOOK_SECRET")
                    kwargs = {
                        "url": webhook_url,
                        "allowed_updates": Update.ALL_TYPES,
                    }
                    if secret:
                        kwargs["secret_token"] = secret

                    run(app.bot.set_webhook(**kwargs))
                    self._send(
                        200,
                        f"Webhook successfully configured to: {webhook_url}"
                    )
                except Exception as exc:
                    self._send(500, f"Webhook setup failed: {exc}")
                return

            self._send(200, "Telegram Panel Bot is active and running!")
            return

        self._send(404, "Not Found")

    def do_POST(self):
        token = os.environ.get("BOT_TOKEN")
        if not token:
            self._send(500, "BOT_TOKEN missing")
            return

        secret = os.environ.get("WEBHOOK_SECRET")
        if secret and secret != "change-this-secret":
            header_secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if header_secret != secret:
                self._send(403, "Forbidden")
                return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            if not raw:
                self._send(200, "OK")
                return
                
            data = json.loads(raw.decode("utf-8"))

            run(initialize_app())

            update = Update.de_json(data, app.bot)
            run(app.process_update(update))

            self._send(200, "OK")
        except Exception as exc:
            print("Webhook error:", repr(exc))
            self._send(500, f"Internal Server Error: {exc}")
