#!/usr/bin/env python3
"""
Physical device: Jetson Nano

Run this file on the Jetson Nano connected to the phone hotspot.
It opens a WebSocket echo server on ws://0.0.0.0:3000 so the phone
browser can verify basic network connectivity.
"""

import asyncio
import socket
import sys

import websockets


HOST = "0.0.0.0"
PORT = 3000


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
    print(f"listening target: ws://{HOST}:{PORT}")
    print("phone target should be: ws://<JETSON_HOTSPOT_IP>:3000")

    try:
        hostname = socket.gethostname()
        print("hostname:", hostname)
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            print("detected IPv4:", info[4][0])
    except Exception as exc:
        print("could not inspect local IP addresses:", exc)

    print("")
    print("If the phone cannot connect, check on Jetson:")
    print("  hostname -I")
    print("  ss -ltnp | grep 3000")
    print("Expected listener: 0.0.0.0:3000")
    print("")


def check_port_available():
    print(f"Port {PORT} bind check:")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        sock.bind((HOST, PORT))
        print(f"OK: port {PORT} is available.")
    except OSError as exc:
        print(f"Port {PORT} is not available:", exc)
        print("Another process may already be using it.")
        print("Check with: ss -ltnp | grep 3000")
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


async def main():
    print_startup_diagnostics()
    async with websockets.serve(handler, HOST, PORT):
        print("WebSocket server is ready.")
        await asyncio.Future()


if __name__ == "__main__":
    if "--diagnose" in sys.argv:
        run_diagnose_only()
    else:
        asyncio.run(main())
