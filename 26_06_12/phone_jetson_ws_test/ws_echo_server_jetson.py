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


def print_python_info():
    print("Python executable:", sys.executable)
    print("Python version:", sys.version.replace("\n", " "))

    try:
        print("websockets package:", websockets.__version__)
    except Exception as exc:
        print("websockets package: NOT IMPORTABLE")
        print("reason:", exc)
        print("fix: python3 -m pip install websockets")


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
