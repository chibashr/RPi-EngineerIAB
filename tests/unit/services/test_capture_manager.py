import pytest

from services.capture_manager import manager as capture_manager


@pytest.mark.unit
def test_split_bpf_filter_rejects_flags():
    with pytest.raises(ValueError):
        capture_manager.split_bpf_filter("-w output.pcap")


@pytest.mark.unit
def test_start_and_stop_capture_dry_run(tmp_path, monkeypatch):
    monkeypatch.setattr(capture_manager, "_capture_dir", lambda: tmp_path)
    manager = capture_manager.CaptureManager()
    monkeypatch.setattr(manager._network_manager, "list_interfaces", lambda: {"interfaces": [{"id": "eth0"}]})

    payload = manager.start_capture({"interface": "eth0", "name": "test-capture"})
    assert payload["interface"] == "eth0"

    captures = manager.list_active()["captures"]
    assert len(captures) == 1

    stopped = manager.stop_capture(payload["capture_id"])
    assert stopped["stopped_at"]
    assert manager.list_completed()["captures"]


@pytest.mark.unit
def test_get_stats_returns_defaults_without_tshark(tmp_path, monkeypatch):
    monkeypatch.setattr(capture_manager, "_capture_dir", lambda: tmp_path)
    manager = capture_manager.CaptureManager()
    monkeypatch.setattr(capture_manager, "_which", lambda _: None)

    job_payload = manager.start_capture({"interface": "eth0", "name": "stat-capture"})
    job = manager.get_job(job_payload["capture_id"])
    assert job and job.file_path
    job.file_path.write_bytes(b"\x00\x01")
    manager.stop_capture(job_payload["capture_id"])

    stats = manager.get_stats(job_payload["capture_id"])
    assert stats["packet_count"] == 0
    assert stats["byte_count"] == 0
