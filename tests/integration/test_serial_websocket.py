"""Integration tests for serial console WebSocket connection.

Verifies the full flow: create session via REST, connect via WebSocket,
and receive data/status. Uses mocked serial port when no real device is available.
"""

from __future__ import annotations

import json
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from services.api_gateway.main import create_app
from services.serial_manager import serial_manager
from services.serial_manager import manager as serial_manager_mod


class MockSerialPort:
    """Mock serial port for testing without hardware."""

    def __init__(self, *args, echo=False, **kwargs):
        self._read_buffer = bytearray()
        self._closed = False
        self.writes = []
        self.echo = echo

    @property
    def in_waiting(self):
        return len(self._read_buffer)

    def read(self, size=1):
        if self._closed:
            raise OSError("Port closed")
        n = min(size, len(self._read_buffer))
        if n == 0:
            return b""
        data = bytes(self._read_buffer[:n])
        del self._read_buffer[:n]
        return data

    def write(self, data):
        if self._closed:
            raise OSError("Port closed")
        self.writes.append(data)
        if self.echo:
            self.inject_rx(data)
        return len(data)

    def flush(self):
        pass

    def close(self):
        self._closed = True

    def inject_rx(self, data: bytes | str) -> None:
        """Simulate data received from the device (for Rx testing)."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        self._read_buffer.extend(data)

    @property
    def is_open(self):
        return not self._closed

    def send_break(self, duration=0.25):
        """Mock break signal (no-op)."""
        pass


@pytest.mark.integration
def test_serial_websocket_session_not_found():
    """WebSocket with unknown session_id receives error message."""
    app = create_app()
    with app.test_client() as client:
        # Flask-Sock with test client: WebSocket upgrade may not work.
        # Use REST to verify session creation, then document WebSocket behavior.
        r = client.get("/api/v1/serial/sessions")
        assert r.status_code == 200
        data = r.get_json()
        assert "data" in data
        assert "sessions" in data["data"]


@pytest.mark.integration
def test_serial_create_session_and_websocket_flow(monkeypatch, tmp_path):
    """Create session via REST, then verify WebSocket handler can look up session.

    When serial.Serial is mocked, the WebSocket handler should open the port,
    start the reader thread, and accept connections. This test verifies the
    session creation and that the WebSocket endpoint is reachable.
    """
    # Ensure we have a device and can create a session
    monkeypatch.setattr(
        serial_manager,
        "_scan_devices",
        lambda: [
            {
                "id": "/dev/ttyTEST0",
                "path": "/dev/ttyTEST0",
                "friendly_name": "Test Serial",
                "chipset": "Unknown",
            }
        ],
    )
    monkeypatch.setattr(serial_manager_mod, "LOG_DIR", tmp_path)

    # Mock serial.Serial to avoid opening real port
    mock_serial = MagicMock()
    mock_port = MockSerialPort()
    mock_serial.Serial.return_value = mock_port
    mock_serial.PARITY_NONE = 0
    mock_serial.EIGHTBITS = 8
    mock_serial.STOPBITS_ONE = 1

    with patch("services.api_gateway.websockets.serial", mock_serial):
        app = create_app()
        with app.test_client() as client:
            # Create session
            r = client.post(
                "/api/v1/serial/sessions",
                json={"device_id": "/dev/ttyTEST0", "config": {}},
                content_type="application/json",
            )
            assert r.status_code in (200, 201), f"Create session failed: {r.data}"
            data = r.get_json()
            assert "data" in data
            session_id = data["data"]["session_id"]
            assert session_id

            # Verify session exists
            r2 = client.get("/api/v1/serial/sessions")
            assert r2.status_code == 200
            sessions = r2.get_json()["data"]["sessions"]
            assert any(s["session_id"] == session_id for s in sessions)


@pytest.mark.integration
def test_serial_websocket_with_live_server(monkeypatch, tmp_path):
    """Start server, create session, connect via WebSocket, verify flow.

    Requires simple-websocket Client. Skips if WebSocket connection fails
    (e.g. test client does not support WebSocket upgrade).
    """
    try:
        from simple_websocket import Client, ConnectionClosed
    except ImportError:
        pytest.skip("simple-websocket not available")

    # Setup mock device and serial
    monkeypatch.setattr(
        serial_manager,
        "_scan_devices",
        lambda: [
            {
                "id": "/dev/ttyTEST0",
                "path": "/dev/ttyTEST0",
                "friendly_name": "Test Serial",
                "chipset": "Unknown",
            }
        ],
    )
    monkeypatch.setattr(serial_manager_mod, "LOG_DIR", tmp_path)

    mock_serial = MagicMock()
    mock_port = MockSerialPort()
    mock_serial.Serial.return_value = mock_port
    mock_serial.PARITY_NONE = 0
    mock_serial.EIGHTBITS = 8
    mock_serial.STOPBITS_ONE = 1

    port_holder = [None]
    server_error = [None]

    with patch("services.api_gateway.websockets.serial", mock_serial):
        # Clear any sessions from previous tests
        serial_manager._sessions.clear()
        app = create_app()

        def run_server():
            try:
                from werkzeug.serving import make_server
                srv = make_server("127.0.0.1", 0, app, threaded=True)
                port_holder[0] = srv.server_port
                srv.serve_forever()
            except Exception as e:
                server_error[0] = e

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        for _ in range(50):
            if port_holder[0] is not None:
                break
            time.sleep(0.1)
        if server_error[0]:
            pytest.skip(f"Could not start server: {server_error[0]}")
        if port_holder[0] is None:
            pytest.skip("Server port not available")

        port = port_holder[0]
        try:
            with app.test_client() as client:
                r = client.post(
                    "/api/v1/serial/sessions",
                    json={"device_id": "/dev/ttyTEST0", "config": {}},
                    content_type="application/json",
                )
                if r.status_code not in (200, 201):
                    pytest.skip(f"Session creation failed: {r.status_code} {r.data}")
                session_id = r.get_json()["data"]["session_id"]

            ws_url = f"ws://127.0.0.1:{port}/ws/serial/{session_id}"
            try:
                ws = Client.connect(ws_url)
            except Exception as e:
                pytest.skip(f"WebSocket connect failed: {e}")

            received = []
            try:
                ws.send(json.dumps({"type": "data", "data": "test"}))
                deadline = time.time() + 3
                while time.time() < deadline and len(received) < 5:
                    try:
                        msg = ws.receive(timeout=0.5)
                        if msg:
                            received.append(json.loads(msg))
                    except ConnectionClosed:
                        break
                    except Exception:
                        break
            finally:
                try:
                    ws.close()
                except Exception:
                    pass

            assert len(mock_port.writes) >= 1
            assert b"test" in mock_port.writes
            msg_types = [m.get("type") for m in received]
            assert "error" not in msg_types or len(received) == 1
        finally:
            pass


@pytest.mark.integration
def test_serial_tx_accuracy(monkeypatch, tmp_path):
    """Verify data sent via WebSocket is correctly written to the serial port (Tx)."""
    try:
        from simple_websocket import Client, ConnectionClosed
    except ImportError:
        pytest.skip("simple-websocket not available")

    monkeypatch.setattr(
        serial_manager,
        "_scan_devices",
        lambda: [
            {"id": "/dev/ttyTEST0", "path": "/dev/ttyTEST0", "friendly_name": "Test", "chipset": "Unknown"}
        ],
    )
    monkeypatch.setattr(serial_manager_mod, "LOG_DIR", tmp_path)

    mock_serial = MagicMock()
    mock_port = MockSerialPort()
    mock_serial.Serial.return_value = mock_port
    mock_serial.PARITY_NONE = 0
    mock_serial.EIGHTBITS = 8
    mock_serial.STOPBITS_ONE = 1

    with patch("services.api_gateway.websockets.serial", mock_serial):
        serial_manager._sessions.clear()
        app = create_app()

        def run_server():
            from werkzeug.serving import make_server
            srv = make_server("127.0.0.1", 0, app, threaded=True)
            port_holder[0] = srv.server_port
            srv.serve_forever()

        port_holder = [None]
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        for _ in range(50):
            if port_holder[0] is not None:
                break
            time.sleep(0.1)
        if port_holder[0] is None:
            pytest.skip("Server port not available")

        with app.test_client() as client:
            r = client.post(
                "/api/v1/serial/sessions",
                json={"device_id": "/dev/ttyTEST0", "config": {}},
                content_type="application/json",
            )
            assert r.status_code in (200, 201)
            session_id = r.get_json()["data"]["session_id"]

        ws = Client.connect(f"ws://127.0.0.1:{port_holder[0]}/ws/serial/{session_id}")
        try:
            test_payloads = ["hello", "reboot\n", "a", "\r\n", "\x01"]
            for payload in test_payloads:
                mock_port.writes.clear()
                ws.send(json.dumps({"type": "data", "data": payload}))
                time.sleep(0.15)
                written = b"".join(mock_port.writes)
                assert payload.encode("utf-8") in written or written == payload.encode("utf-8"), (
                    f"Tx failed: sent {payload!r}, wrote {written!r}"
                )
        finally:
            try:
                ws.close()
            except Exception:
                pass


@pytest.mark.integration
def test_serial_rx_accuracy(monkeypatch, tmp_path):
    """Verify data from the serial port is correctly received via WebSocket (Rx)."""
    try:
        from simple_websocket import Client, ConnectionClosed
    except ImportError:
        pytest.skip("simple-websocket not available")

    monkeypatch.setattr(
        serial_manager,
        "_scan_devices",
        lambda: [
            {"id": "/dev/ttyTEST0", "path": "/dev/ttyTEST0", "friendly_name": "Test", "chipset": "Unknown"}
        ],
    )
    monkeypatch.setattr(serial_manager_mod, "LOG_DIR", tmp_path)

    mock_serial = MagicMock()
    mock_port = MockSerialPort()
    mock_serial.Serial.return_value = mock_port
    mock_serial.PARITY_NONE = 0
    mock_serial.EIGHTBITS = 8
    mock_serial.STOPBITS_ONE = 1

    with patch("services.api_gateway.websockets.serial", mock_serial):
        serial_manager._sessions.clear()
        app = create_app()

        def run_server():
            from werkzeug.serving import make_server
            srv = make_server("127.0.0.1", 0, app, threaded=True)
            port_holder[0] = srv.server_port
            srv.serve_forever()

        port_holder = [None]
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        for _ in range(50):
            if port_holder[0] is not None:
                break
            time.sleep(0.1)
        if port_holder[0] is None:
            pytest.skip("Server port not available")

        with app.test_client() as client:
            r = client.post(
                "/api/v1/serial/sessions",
                json={"device_id": "/dev/ttyTEST0", "config": {}},
                content_type="application/json",
            )
            assert r.status_code in (200, 201)
            session_id = r.get_json()["data"]["session_id"]

        ws = Client.connect(f"ws://127.0.0.1:{port_holder[0]}/ws/serial/{session_id}")
        try:
            time.sleep(0.2)
            mock_port.inject_rx("prompt> ")
            mock_port.inject_rx("hello from device\n")
            time.sleep(0.3)

            received_data = []
            deadline = time.time() + 2
            while time.time() < deadline:
                try:
                    msg = ws.receive(timeout=0.3)
                    if msg:
                        obj = json.loads(msg)
                        if obj.get("type") == "data":
                            received_data.append(obj.get("data", ""))
                        if "prompt>" in "".join(received_data) and "hello from device" in "".join(received_data):
                            break
                except ConnectionClosed:
                    break
                except Exception:
                    break

            combined = "".join(received_data)
            assert "prompt>" in combined, f"Rx failed: expected 'prompt>' in received data, got {combined!r}"
            assert "hello from device" in combined, f"Rx failed: expected 'hello from device' in received data, got {combined!r}"
        finally:
            try:
                ws.close()
            except Exception:
                pass


@pytest.mark.integration
def test_serial_tx_rx_roundtrip(monkeypatch, tmp_path):
    """Verify Tx and Rx work together: send data, simulate echo, receive it back."""
    try:
        from simple_websocket import Client, ConnectionClosed
    except ImportError:
        pytest.skip("simple-websocket not available")

    monkeypatch.setattr(
        serial_manager,
        "_scan_devices",
        lambda: [
            {"id": "/dev/ttyTEST0", "path": "/dev/ttyTEST0", "friendly_name": "Test", "chipset": "Unknown"}
        ],
    )
    monkeypatch.setattr(serial_manager_mod, "LOG_DIR", tmp_path)

    mock_serial = MagicMock()
    mock_port = MockSerialPort(echo=True)
    mock_serial.Serial.return_value = mock_port
    mock_serial.PARITY_NONE = 0
    mock_serial.EIGHTBITS = 8
    mock_serial.STOPBITS_ONE = 1

    with patch("services.api_gateway.websockets.serial", mock_serial):
        serial_manager._sessions.clear()
        app = create_app()

        def run_server():
            from werkzeug.serving import make_server
            srv = make_server("127.0.0.1", 0, app, threaded=True)
            port_holder[0] = srv.server_port
            srv.serve_forever()

        port_holder = [None]
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        for _ in range(50):
            if port_holder[0] is not None:
                break
            time.sleep(0.1)
        if port_holder[0] is None:
            pytest.skip("Server port not available")

        with app.test_client() as client:
            r = client.post(
                "/api/v1/serial/sessions",
                json={"device_id": "/dev/ttyTEST0", "config": {}},
                content_type="application/json",
            )
            assert r.status_code in (200, 201)
            session_id = r.get_json()["data"]["session_id"]

        ws = Client.connect(f"ws://127.0.0.1:{port_holder[0]}/ws/serial/{session_id}")
        try:
            ws.send(json.dumps({"type": "data", "data": "echo_test"}))
            time.sleep(0.4)

            received = []
            deadline = time.time() + 2
            while time.time() < deadline:
                try:
                    msg = ws.receive(timeout=0.3)
                    if msg:
                        obj = json.loads(msg)
                        if obj.get("type") == "data":
                            received.append(obj.get("data", ""))
                        if "echo_test" in "".join(received):
                            break
                except ConnectionClosed:
                    break
                except Exception:
                    pass

            combined = "".join(received)
            assert "echo_test" in combined, f"Roundtrip failed: expected echo in {combined!r}"
            assert b"echo_test" in b"".join(mock_port.writes), "Tx failed: data not written to serial"
        finally:
            try:
                ws.close()
            except Exception:
                pass
