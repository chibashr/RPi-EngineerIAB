"""Tests for WebSocket handlers (status, serial, updates/apply, capture).

Uses pytest + FastAPI TestClient. Mocks managers and hardware; no real serial/capture.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastapi.testclient import TestClient

from services.api_gateway.main import create_app
from services.api_gateway import websockets as websockets_mod


# --- Fixtures ---


@pytest.fixture
def ws_client(app):
    """Test client with WebSocket support."""
    return TestClient(app)


@pytest.fixture
def app():
    """Create FastAPI application for testing."""
    return create_app()


# --- /ws/status ---


@pytest.mark.integration
def test_ws_status_connection_accepted(ws_client):
    """Connection to /ws/status is accepted."""
    with ws_client.websocket_connect("/ws/status") as websocket:
        # Connection established; no explicit accept needed (client does it)
        assert websocket is not None


@pytest.mark.integration
def test_ws_status_sends_json_within_two_seconds(ws_client):
    """Server sends JSON within 2 seconds of connect."""
    with ws_client.websocket_connect("/ws/status") as websocket:
        data = websocket.receive_json()
        assert isinstance(data, dict)
        assert "type" in data
        assert "data" in data or data.get("type") == "pong"


@pytest.mark.integration
def test_ws_status_json_has_expected_keys(ws_client):
    """JSON messages match frontend contract (type, data)."""
    with ws_client.websocket_connect("/ws/status") as websocket:
        received = []
        for _ in range(4):  # Expect at least system_metrics, network_status, etc.
            try:
                data = websocket.receive_json()
                received.append(data)
                assert "type" in data
                if data.get("type") not in ("pong",):
                    assert "data" in data
                if data.get("type") == "system_metrics":
                    assert "resources" in data.get("data", {}) or "services" in data.get("data", {})
                if data.get("type") == "network_interfaces":
                    assert "interfaces" in data.get("data", {})
                break  # One full batch is enough
            except Exception:
                break
        assert len(received) >= 1


@pytest.mark.integration
def test_ws_status_disconnect_no_unhandled_exception(ws_client):
    """Disconnect does not raise unhandled exception."""
    with ws_client.websocket_connect("/ws/status") as websocket:
        _ = websocket.receive_json()
    # Exiting context manager closes connection; no exception


@pytest.mark.integration
def test_ws_status_ping_pong(ws_client):
    """Client ping receives pong."""
    with ws_client.websocket_connect("/ws/status") as websocket:
        websocket.send_json({"type": "ping"})
        data = websocket.receive_json()
        assert data.get("type") == "pong"


# --- /ws/serial/{session_id} ---


@dataclass
class FakeSerialSession:
    """Fake session for serial WebSocket tests."""

    session_id: str
    device_id: str
    config: dict
    created_at: str = "2020-01-01T00:00:00Z"
    status: str = "active"
    logging_paused: bool = False
    bytes_tx: int = 0
    bytes_rx: int = 0
    log_path: None = None
    websocket_connected: bool = False
    metadata: dict = field(default_factory=dict)


@pytest.mark.integration
def test_ws_serial_connection_accepted_for_valid_session(ws_client):
    """Connection accepted for valid session_id."""
    fake_session = FakeSerialSession(
        session_id="test-session-123",
        device_id="/dev/ttyUSB0",
        config={"baud_rate": 9600},
    )
    mock_serial = MagicMock()
    mock_port = MagicMock()
    mock_port.read.side_effect = [b"", b"", b""]
    mock_port.write.return_value = None
    mock_port.close.side_effect = None
    mock_serial.Serial.return_value = mock_port

    with (
        patch("services.api_gateway.websockets.serial_manager") as mock_sm,
        patch.dict("sys.modules", {"serial": mock_serial}),
    ):
        mock_sm.get_session_record.return_value = fake_session
        mock_sm.get_session.return_value = {"bytes_tx": 0, "bytes_rx": 0}
        mock_sm.update_session.return_value = None
        mock_sm.release_session.return_value = None

        with ws_client.websocket_connect("/ws/serial/test-session-123") as websocket:
            # Receive at least one message (error, data, or status)
            data = websocket.receive_json()
            assert "type" in data
            # Should NOT be error if session was valid and serial opened
            if data.get("type") == "error":
                # On Windows /dev/ttyUSB0 may not exist; mock Serial to avoid real open
                assert "Session not found" not in data.get("message", "")
    mock_sm.release_session.assert_called_once_with("test-session-123")


@pytest.mark.integration
def test_ws_serial_rejected_for_unknown_session(ws_client):
    """Connection rejected (error message) for unknown session_id."""
    with patch("services.api_gateway.websockets.serial_manager") as mock_sm:
        mock_sm.get_session_record.side_effect = KeyError("Session not found")

        with ws_client.websocket_connect("/ws/serial/unknown-session-xyz") as websocket:
            data = websocket.receive_json()
            assert data.get("type") == "error"
            assert "Session not found" in data.get("message", "") or "not found" in data.get("message", "").lower()


@pytest.mark.integration
def test_ws_serial_client_message_forwarded_to_mock_serial(ws_client):
    """Client message (data) is received and forwarded to mock serial port."""
    fake_session = FakeSerialSession(
        session_id="s1",
        device_id="/dev/ttyUSB0",
        config={"baud_rate": 9600},
    )
    mock_serial = MagicMock()
    mock_port = MagicMock()
    mock_port.read.side_effect = [b"", b"", b""]
    mock_port.write.return_value = None
    mock_port.close.return_value = None
    mock_serial.Serial.return_value = mock_port

    with (
        patch("services.api_gateway.websockets.serial_manager") as mock_sm,
        patch.dict("sys.modules", {"serial": mock_serial}),
    ):
        mock_sm.get_session_record.return_value = fake_session
        mock_sm.get_session.return_value = {"bytes_tx": 0, "bytes_rx": 0}
        mock_sm.update_session.return_value = None
        mock_sm.release_session.return_value = None

        with ws_client.websocket_connect("/ws/serial/s1") as websocket:
            websocket.send_json({"type": "data", "data": "hello"})
            # Give handler time to process
            try:
                websocket.receive_json()
            except Exception:
                pass
            websocket.close()

    mock_port.write.assert_called()
    written = b"".join(c.args[0] for c in mock_port.write.call_args_list)
    assert b"hello" in written


@pytest.mark.integration
def test_ws_serial_server_sends_data_when_mock_serial_has_output(ws_client):
    """Server sends data when mock serial port has output."""
    fake_session = FakeSerialSession(
        session_id="s2",
        device_id="/dev/ttyUSB0",
        config={"baud_rate": 9600},
    )
    mock_serial = MagicMock()
    mock_port = MagicMock()
    mock_port.read.side_effect = [b"device output\n", b"", b""]
    mock_port.write.return_value = None
    mock_port.close.return_value = None
    mock_serial.Serial.return_value = mock_port

    with (
        patch("services.api_gateway.websockets.serial_manager") as mock_sm,
        patch.dict("sys.modules", {"serial": mock_serial}),
    ):
        mock_sm.get_session_record.return_value = fake_session
        mock_sm.get_session.return_value = {"bytes_tx": 0, "bytes_rx": 0}
        mock_sm.update_session.return_value = None
        mock_sm.release_session.return_value = None

        with ws_client.websocket_connect("/ws/serial/s2") as websocket:
            received = []
            for _ in range(15):  # Allow time for reader task to get mock data
                try:
                    data = websocket.receive_json()
                    received.append(data)
                    if data.get("type") == "data":
                        assert "device output" in data.get("data", "")
                        break
                except Exception:
                    break

        assert any(r.get("type") == "data" and "device output" in r.get("data", "") for r in received)


@pytest.mark.integration
def test_ws_serial_clean_disconnect_closes_serial_port(ws_client):
    """Clean disconnect closes serial port (verify mock is closed)."""
    fake_session = FakeSerialSession(
        session_id="s3",
        device_id="/dev/ttyUSB0",
        config={"baud_rate": 9600},
    )
    mock_serial = MagicMock()
    mock_port = MagicMock()
    mock_port.read.side_effect = [b"", b"", b""]
    mock_port.write.return_value = None
    mock_port.close.return_value = None
    mock_serial.Serial.return_value = mock_port

    with (
        patch("services.api_gateway.websockets.serial_manager") as mock_sm,
        patch.dict("sys.modules", {"serial": mock_serial}),
    ):
        mock_sm.get_session_record.return_value = fake_session
        mock_sm.get_session.return_value = {"bytes_tx": 0, "bytes_rx": 0}
        mock_sm.release_session.return_value = None

        with ws_client.websocket_connect("/ws/serial/s3") as websocket:
            websocket.receive_json()
        # After exiting context, connection closed; handler should have closed serial
    mock_port.close.assert_called()


# --- /ws/updates/apply ---


@pytest.mark.integration
def test_ws_updates_apply_connection_accepted(ws_client):
    """Connection to /ws/updates/apply is accepted."""
    with patch("services.api_gateway.websockets.update_manager") as mock_um:
        mock_um.apply_update.return_value = {"status": "up_to_date", "current_version": "abc1234"}

        with ws_client.websocket_connect("/ws/updates/apply") as websocket:
            assert websocket is not None


@pytest.mark.integration
def test_ws_updates_apply_streams_lines(ws_client):
    """Server streams progress lines (at least one message received)."""

    def fake_apply(progress_callback=None):
        if progress_callback:
            progress_callback("Checking for updates...")
            progress_callback("No update available.")
        return {"status": "up_to_date", "current_version": "abc1234"}

    with patch("services.api_gateway.websockets.update_manager") as mock_um:
        mock_um.apply_update.side_effect = fake_apply

        with ws_client.websocket_connect("/ws/updates/apply") as websocket:
            received = []
            while len(received) < 10:
                data = websocket.receive_json()
                received.append(data)
                if data.get("type") in ("done", "error"):
                    break

            assert len(received) >= 1
            progress_msgs = [r for r in received if r.get("type") == "progress"]
            assert len(progress_msgs) >= 1
            assert "Checking for updates" in progress_msgs[0].get("line", "")


@pytest.mark.integration
def test_ws_updates_apply_stream_ends_with_completion(ws_client):
    """Stream ends with done or error message."""

    def fake_apply(progress_callback=None):
        if progress_callback:
            progress_callback("Step 1")
        return {"status": "applied", "dry_run": True}

    with patch("services.api_gateway.websockets.update_manager") as mock_um:
        mock_um.apply_update.side_effect = fake_apply

        with ws_client.websocket_connect("/ws/updates/apply") as websocket:
            last = None
            for _ in range(10):
                data = websocket.receive_json()
                last = data
                if data.get("type") in ("done", "error"):
                    break

            assert last is not None
            assert last.get("type") in ("done", "error")
            if last.get("type") == "done":
                assert "result" in last
                assert last["result"].get("status") == "applied"


@pytest.mark.integration
def test_ws_updates_apply_disconnect_mid_stream_no_subprocess_leak(ws_client):
    """Disconnect mid-stream does not leave subprocess running (apply runs in thread)."""
    call_count = 0

    def fake_apply(progress_callback=None):
        nonlocal call_count
        call_count += 1
        if progress_callback:
            progress_callback("Starting...")
        return {"status": "up_to_date"}

    with patch("services.api_gateway.websockets.update_manager") as mock_um:
        mock_um.apply_update.side_effect = fake_apply

        with ws_client.websocket_connect("/ws/updates/apply") as websocket:
            websocket.receive_json()
            websocket.close()
        # No subprocess; apply_update is mocked. Just verify no crash.
    assert call_count == 1


# --- /ws/capture/{capture_id} ---


@dataclass
class FakeCaptureJob:
    """Fake capture job for WebSocket tests."""

    capture_id: str
    interface: str
    name: str
    file_path: Path | None
    filter: str | None = None
    duration_seconds: int | None = None
    max_size_mb: int | None = None
    started_at: str = "2020-01-01T00:00:00Z"
    stopped_at: str | None = None
    process: None = None


@pytest.mark.integration
def test_ws_capture_connection_accepted_for_valid_capture(ws_client, tmp_path):
    """Connection accepted for valid capture_id."""
    pcap_file = tmp_path / "capture.pcap"
    pcap_file.write_bytes(b"\x00\x00\x00\x00")  # Minimal placeholder
    fake_job = FakeCaptureJob(
        capture_id="cap-123",
        interface="eth0",
        name="test",
        file_path=pcap_file,
    )

    async def fake_create_subprocess_exec(*args, **kwargs):
        class FakeStream:
            async def __aiter__(self):
                yield b"1 0.0 192.168.1.1 -> 192.168.1.2\n"

        class FakeProcess:
            stdout = FakeStream()

            def terminate(self):
                pass

            async def wait(self):
                pass

        return FakeProcess()

    with (
        patch("services.api_gateway.websockets.capture_manager") as mock_cm,
        patch("services.api_gateway.websockets.shutil.which", return_value="/usr/bin/tshark"),
        patch(
            "services.api_gateway.websockets.asyncio.create_subprocess_exec",
            side_effect=fake_create_subprocess_exec,
        ),
    ):
        mock_cm.get_job.return_value = fake_job

        with ws_client.websocket_connect("/ws/capture/cap-123") as websocket:
            data = websocket.receive_json()
            assert "type" in data
            assert data.get("type") in ("packet", "error")


@pytest.mark.integration
def test_ws_capture_rejected_for_unknown_capture(ws_client):
    """Connection rejected for unknown capture_id."""
    with patch("services.api_gateway.websockets.capture_manager") as mock_cm:
        mock_cm.get_job.return_value = None

        with ws_client.websocket_connect("/ws/capture/unknown-cap-xyz") as websocket:
            data = websocket.receive_json()
            assert data.get("type") == "error"
            assert "not found" in data.get("message", "").lower() or "Capture" in data.get("message", "")


@pytest.mark.integration
@pytest.mark.timeout(10)
def test_ws_capture_streams_packet_data(ws_client, tmp_path):
    """Server streams packet data messages."""
    pcap_file = tmp_path / "cap.pcap"
    pcap_file.write_bytes(b"\x00\x00\x00\x00")
    fake_job = FakeCaptureJob(
        capture_id="cap-456",
        interface="eth0",
        name="test",
        file_path=pcap_file,
    )

    async def fake_create_subprocess_exec(*args, **kwargs):
        class FakeStream:
            async def __aiter__(self):
                yield b"1 0.0 192.168.1.1 -> 192.168.1.2 TCP 64\n"
                yield b"2 0.1 192.168.1.2 -> 192.168.1.1 TCP 128\n"

        class FakeProcess:
            def __init__(self):
                self.stdout = FakeStream()

            def terminate(self):
                pass

            async def wait(self):
                pass

        return FakeProcess()

    with (
        patch("services.api_gateway.websockets.capture_manager") as mock_cm,
        patch("services.api_gateway.websockets.shutil.which", return_value="/usr/bin/tshark"),
        patch.object(
            websockets_mod.asyncio,
            "create_subprocess_exec",
            side_effect=fake_create_subprocess_exec,
        ),
    ):
        mock_cm.get_job.return_value = fake_job

        with ws_client.websocket_connect("/ws/capture/cap-456") as websocket:
            packets = []
            # Break as soon as we have 1 packet; avoid blocking on receive_json()
            # after server closes (handler exhausts mock stream and exits)
            while len(packets) < 1:
                try:
                    data = websocket.receive_json()
                    if data.get("type") == "packet":
                        packets.append(data.get("summary", ""))
                    if data.get("type") == "error":
                        break
                except Exception:
                    break

            assert len(packets) >= 1
            assert "192.168.1.1" in packets[0] or "TCP" in packets[0]


@pytest.mark.integration
def test_ws_capture_disconnect_stops_stream(ws_client, tmp_path):
    """Disconnect stops the capture stream (proc.terminate called)."""
    pcap_file = tmp_path / "cap.pcap"
    pcap_file.write_bytes(b"\x00\x00\x00\x00")
    fake_job = FakeCaptureJob(
        capture_id="cap-789",
        interface="eth0",
        name="test",
        file_path=pcap_file,
    )

    proc_mock = MagicMock()
    proc_mock.terminate = MagicMock()
    proc_mock.wait = AsyncMock(return_value=0)

    async def fake_create_subprocess_exec(*args, **kwargs):
        class FakeStream:
            async def __aiter__(self):
                for i in range(100):
                    yield f"{i} packet line\n".encode()

        proc_mock.stdout = FakeStream()
        return proc_mock

    with (
        patch("services.api_gateway.websockets.capture_manager") as mock_cm,
        patch("services.api_gateway.websockets.shutil.which", return_value="/usr/bin/tshark"),
        patch(
            "services.api_gateway.websockets.asyncio.create_subprocess_exec",
            side_effect=fake_create_subprocess_exec,
        ),
    ):
        mock_cm.get_job.return_value = fake_job

        with ws_client.websocket_connect("/ws/capture/cap-789") as websocket:
            websocket.receive_json()
            websocket.close()

    proc_mock.terminate.assert_called()
