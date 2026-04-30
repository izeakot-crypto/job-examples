#!/usr/bin/env python3
"""
Простий HTTP-приймач для отримання файлів через curl.
Запуск: python receive_file.py
Порт: 9999
"""
import http.server
import os
import sys

PORT = 9999
SAVE_DIR = os.path.dirname(os.path.abspath(__file__))

class FileReceiver(http.server.BaseHTTPRequestHandler):
    def do_PUT(self):
        # Ім'я файлу з URL path
        filename = os.path.basename(self.path.strip('/')) or 'uploaded_file'
        filepath = os.path.join(SAVE_DIR, filename)

        length = int(self.headers.get('Content-Length', 0))
        data = self.rfile.read(length)

        with open(filepath, 'wb') as f:
            f.write(data)

        print(f"\n  RECEIVED: {filename} ({len(data)} bytes)")
        print(f"  SAVED TO: {filepath}\n")

        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(f"OK: {filename} saved ({len(data)} bytes)\n".encode())

    def do_POST(self):
        self.do_PUT()

    def log_message(self, format, *args):
        pass  # suppress default logs

if __name__ == '__main__':
    print(f"Listening on 0.0.0.0:{PORT}")
    print(f"Save directory: {SAVE_DIR}")
    print(f"Waiting for file...\n")
    server = http.server.HTTPServer(('0.0.0.0', PORT), FileReceiver)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
