"""Unit tests for BPF filter parsing in capture manager."""

from __future__ import annotations

import pytest

from services.capture_manager.manager import split_bpf_filter


class TestSplitBpfFilter:
    """Tests for split_bpf_filter."""

    def test_empty_string_returns_empty_list(self):
        assert split_bpf_filter("") == []

    def test_single_token(self):
        assert split_bpf_filter("tcp") == ["tcp"]

    def test_multiple_tokens(self):
        assert split_bpf_filter("tcp port 80") == ["tcp", "port", "80"]

    def test_quoted_string_preserved(self):
        assert split_bpf_filter('host "192.168.1.1"') == ["host", "192.168.1.1"]

    def test_complex_filter(self):
        result = split_bpf_filter("tcp port 443 and host 10.0.0.1")
        assert "tcp" in result
        assert "port" in result
        assert "443" in result
        assert "and" in result
        assert "host" in result
        assert "10.0.0.1" in result

    def test_rejects_dash_prefix(self):
        with pytest.raises(ValueError, match="Invalid filter"):
            split_bpf_filter("-i eth0")

    def test_rejects_tcpdump_style_args(self):
        with pytest.raises(ValueError, match="Invalid filter"):
            split_bpf_filter("-n tcp")
