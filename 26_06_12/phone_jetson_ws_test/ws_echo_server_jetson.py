#!/usr/bin/env python3
"""
Physical device: Jetson Nano

Run this file on the Jetson Nano connected to the phone hotspot.
It opens a WebSocket echo server on ws://0.0.0.0:3000 so the phone
browser can verify basic network connectivity.
"""

import asyncio
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import socket
import subprocess
import sys
from pathlib import Path
from threading import Thread

import websockets


HOST = "0.0.0.0"
WS_PORT = 3000
HTTP_PORT = 8000
THIS_DIR = Path(__file__).resolve().parent
HTML_FILE = THIS_DIR / "phone_ws_client.html"

HTML_TEMPLATE = """<!doctype html>
<!--
Physical device: Phone

Open this page from the phone browser:
http://<JETSON_HOTSPOT_IP>:8000/phone_ws_client.html
-->
<html lang="ko">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Phone-Jetson WebSocket Test</title>
    <style>
        body {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            margin: 24px;
            line-height: 1.5;
        }

        button {
            padding: 12px 16px;
            font-size: 16px;
        }

        pre {
            margin-top: 16px;
            padding: 12px;
            border: 1px solid #ddd;
            background: #f7f7f7;
            white-space: pre-wrap;
        }
    </style>
</head>
<body>
    <h1>Phone-Jetson WebSocket Test</h1>
    <p>Target: <code id="target"></code></p>
    <button type="button" onclick="sendTestMessage()">Send Test Message</button>
    <button type="button" onclick="reconnect()">Reconnect</button>
    <pre id="log"></pre>

    <script>
        const DEFAULT_WS_URL = "ws://10.59.121.144:3000";
        const WS_URL = location.protocol.startsWith("http")
            ? "ws://" + location.hostname + ":3000"
            : DEFAULT_WS_URL;
        const CONNECT_TIMEOUT_MS = 5000;
        const logEl = document.getElementById("log");
        const targetEl = document.getElementById("target");
        let ws = null;
        let connectTimer = null;

        targetEl.textContent = WS_URL;

        function log(message) {
            const now = new Date().toLocaleTimeString();
            logEl.textContent += "[" + now + "] " + message + "\\n";
        }

        function connect() {
            clearTimeout(connectTimer);
            log("connecting: " + WS_URL);
            log("phone online: " + navigator.onLine);
            log("page origin: " + location.origin);

            ws = new WebSocket(WS_URL);

            connectTimer = setTimeout(() => {
                if (ws && ws.readyState !== WebSocket.OPEN) {
                    log("diagnosis: connection timeout after " + CONNECT_TIMEOUT_MS + " ms");
                    log("check 1: Jetson IP in browser URL is correct");
                    log("check 2: Jetson server is running on 0.0.0.0:3000");
                    log("check 3: phone hotspot allows phone-to-Jetson traffic");
                }
            }, CONNECT_TIMEOUT_MS);

            ws.onopen = () => {
                clearTimeout(connectTimer);
                log("connected");
            };

            ws.onmessage = (event) => log("received: " + event.data);
            ws.onerror = () => {
                log("error: browser cannot expose the exact WebSocket network error");
            };
            ws.onclose = (event) => {
                clearTimeout(connectTimer);
                log("closed: code=" + event.code + " reason=" + (event.reason || "(empty)"));
            };
        }

        function reconnect() {
            if (ws) {
                ws.close();
            }
            connect();
        }

        function sendTestMessage() {
            if (!ws || ws.readyState !== WebSocket.OPEN) {
                log("not connected");
                log("diagnosis: send failed because WebSocket is not open");
                return;
            }

            ws.send("hello from phone");
            log("sent: hello from phone");
        }

        connect();
    </script>
</body>
</html>
"""


def print_python_info():
    print("Python executable:", sys.executable)
    print("Python version:", sys.version.replace("\n", " "))

    try:
        print("websockets package:", websockets.__version__)
    except Exception as exc:
        print("websockets package: NOT IMPORTABLE")
        print("reason:", exc)
        print("fix: python3 -m pip install websockets")


def ensure_html_file():
    if HTML_FILE.exists():
        return

    HTML_FILE.write_text(HTML_TEMPLATE, encoding="utf-8")
    print(f"created missing HTML test page: {HTML_FILE}")


def print_startup_diagnostics():
    print("physical device: Jetson Nano")
    print_python_info()
    print(f"WebSocket target: ws://{HOST}:{WS_PORT}")
    print(f"HTTP test page: http://{HOST}:{HTTP_PORT}/phone_ws_client.html")
    print("phone should open: http://<JETSON_HOTSPOT_IP>:8000/phone_ws_client.html")
    print("phone WebSocket target should be: ws://<JETSON_HOTSPOT_IP>:3000")

    print_detected_ips()

    print("")
    print("If the phone cannot connect, check on Jetson:")
    print("  hostname -I")
    print("  ss -ltnp | grep -E '3000|8000'")
    print("Expected listeners: 0.0.0.0:3000 and 0.0.0.0:8000")
    print("")


def run_command(command):
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception as exc:
        return "", str(exc)

    return completed.stdout.strip(), completed.stderr.strip()


def print_detected_ips():
    try:
        print("hostname:", socket.gethostname())
    except Exception as exc:
        print("hostname lookup failed:", exc)

    stdout, stderr = run_command(["hostname", "-I"])
    if stdout:
        print("hostname -I:", stdout)
        first_ipv4 = next((part for part in stdout.split() if "." in part), None)
        if first_ipv4:
            print("")
            print("Use this on the phone browser:")
            print(f"  http://{first_ipv4}:{HTTP_PORT}/phone_ws_client.html")
            print("This page will connect WebSocket to:")
            print(f"  ws://{first_ipv4}:{WS_PORT}")
    elif stderr:
        print("hostname -I error:", stderr)

    stdout, stderr = run_command(["ip", "-4", "addr", "show"])
    if stdout:
        print("")
        print("ip -4 addr show:")
        print(stdout)
    elif stderr:
        print("ip -4 addr show error:", stderr)


def check_port_available():
    for port in (WS_PORT, HTTP_PORT):
        print(f"Port {port} bind check:")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            sock.bind((HOST, port))
            print(f"OK: port {port} is available.")
        except OSError as exc:
            print(f"Port {port} is not available:", exc)
            print("Another process may already be using it.")
            print("Check with: ss -ltnp | grep -E '3000|8000'")
        finally:
            sock.close()


def run_diagnose_only():
    print_startup_diagnostics()
    check_port_available()
    print("")
    print("If the server is running and the phone still cannot connect:")
    print("- confirm the phone and Jetson are on the same phone hotspot")
    print("- confirm the HTML target IP matches the current Jetson IP")
    print("- confirm the server prints 'WebSocket server is ready.'")
    print("- check whether the phone hotspot blocks device-to-device traffic")


async def handler(websocket):
    print("client connected:", websocket.remote_address)

    async for message in websocket:
        print("received:", message)
        await websocket.send("echo: " + message)


def start_http_server():
    handler_class = partial(SimpleHTTPRequestHandler, directory=str(THIS_DIR))
    httpd = ThreadingHTTPServer((HOST, HTTP_PORT), handler_class)
    print(f"HTTP server is ready on http://{HOST}:{HTTP_PORT}/phone_ws_client.html")
    httpd.serve_forever()


async def main():
    ensure_html_file()
    print_startup_diagnostics()
    http_thread = Thread(target=start_http_server, daemon=True)
    http_thread.start()

    async with websockets.serve(handler, HOST, WS_PORT):
        print("WebSocket server is ready.")
        await asyncio.Future()


if __name__ == "__main__":
    if "--diagnose" in sys.argv:
        run_diagnose_only()
    else:
        asyncio.run(main())
