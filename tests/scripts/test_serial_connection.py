#!/usr/bin/env python3
"""Manual script to test serial console WebSocket connection.

Run from project root. Requires:
- API server running (or run with --serve to start it)
- A serial device (or use mock with --mock)

Usage:
  python tests/scripts/test_serial_connection.py --mock
  python tests/scripts/test_serial_connection.py --device /dev/ttyUSB0
  python tests/scripts/test_serial_connection.py --device COM3  # Windows
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main():
    parser = argparse.ArgumentParser(description="Test serial WebSocket connection")
    parser.add_argument("--host", default="127.0.0.1", help="API host")
    parser.add_argument("--port", type=int, default=5000, help="API port")
    parser.add_argument("--device", help="Serial device path (e.g. /dev/ttyUSB0 or COM3)")
    parser.add_argument("--mock", action="store_true", help="Use mock device (no hardware)")
    parser.add_argument("--serve", action="store_true", help="Start API server in background")
    args = parser.parse_args()

    try:
        from simple_websocket import Client, ConnectionClosed
    except ImportError:
        print("ERROR: simple-websocket required. pip install simple-websocket")
        sys.exit(1)

    if args.serve:
        import threading
        from services.api_gateway.main import app
        def run():
            app.run(host=args.host, port=args.port, threaded=True, use_reloader=False)
        t = threading.Thread(target=run, daemon=True)
        t.start()
        time.sleep(2)
        print(f"Server started on {args.host}:{args.port}")

    base_url = f"http://{args.host}:{args.port}"
    ws_base = f"ws://{args.host}:{args.port}"

    try:
        import urllib.request
        r = urllib.request.urlopen(f"{base_url}/api/v1/serial/devices", timeout=5)
        data = json.loads(r.read().decode())
        devices = data.get("data", {}).get("devices", [])
    except Exception as e:
        print(f"ERROR: Cannot reach API at {base_url}: {e}")
        print("Ensure the API is running: python services/api_gateway/main.py")
        sys.exit(1)

    if not devices:
        if args.mock:
            print("No devices found. Run automated mock test instead:")
            print("  pytest tests/integration/test_serial_websocket.py -v")
            sys.exit(0)
        print("ERROR: No serial devices detected. Connect a USB-serial adapter.")
        sys.exit(1)

    device_id = args.device or devices[0]["id"]
    if not any(d["id"] == device_id for d in devices):
        print(f"ERROR: Device {device_id} not in list: {[d['id'] for d in devices]}")
        sys.exit(1)

    print(f"Creating session for device: {device_id}")
    try:
        req = urllib.request.Request(
            f"{base_url}/api/v1/serial/sessions",
            data=json.dumps({"device_id": device_id, "config": {}}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        r = urllib.request.urlopen(req, timeout=5)
        data = json.loads(r.read().decode())
        session_id = data["data"]["session_id"]
        print(f"Session created: {session_id[:8]}...")
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"ERROR: Create session failed {e.code}: {body}")
        sys.exit(1)

    ws_url = f"{ws_base}/ws/serial/{session_id}"
    print(f"Connecting WebSocket: {ws_url}")
    try:
        ws = Client.connect(ws_url)
        print("WebSocket CONNECTED")
        received = 0
        deadline = time.time() + 5
        while time.time() < deadline and received < 10:
            try:
                msg = ws.receive(timeout=1)
                if msg:
                    obj = json.loads(msg)
                    msg_type = obj.get("type", "?")
                    if msg_type == "data":
                        print(f"  DATA: {obj.get('data', '')!r}")
                    elif msg_type == "status":
                        print(f"  STATUS: Tx={obj.get('bytes_tx',0)} Rx={obj.get('bytes_rx',0)}")
                    elif msg_type == "error":
                        print(f"  ERROR: {obj.get('message','')}")
                    received += 1
            except ConnectionClosed:
                print("Connection closed")
                break
        ws.close()
        print(f"Test complete. Received {received} message(s).")
    except Exception as e:
        print(f"ERROR: WebSocket failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
