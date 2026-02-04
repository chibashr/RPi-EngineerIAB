"""SFTP/SCP server implementation for file share."""

from __future__ import annotations

import os
import socket
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import paramiko

from . import user_store


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _data_dir() -> Path:
    env_path = Path(os.getenv("RPI_ENGINEER_DATA_DIR", "/var/lib/rpi-engineer"))
    base = env_path if env_path.exists() else _repo_root() / "data"
    base.mkdir(parents=True, exist_ok=True)
    module_dir = base / "file_share"
    module_dir.mkdir(parents=True, exist_ok=True)
    return module_dir


def _host_key_path() -> Path:
    return _data_dir() / "ssh_host_key"


def _load_host_key() -> paramiko.PKey:
    path = _host_key_path()
    if path.exists():
        return paramiko.RSAKey.from_private_key_file(str(path))
    key = paramiko.RSAKey.generate(2048)
    key.write_private_key_file(str(path))
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


class _SFTPServer(paramiko.SFTPServerInterface):
    def __init__(self, server, share_root: Path):  # type: ignore[no-untyped-def]
        super().__init__(server)
        self._root = share_root

    def _resolve(self, path: str) -> Path:
        rel = Path(path.lstrip("/"))
        full = (self._root / rel).resolve()
        if self._root not in full.parents and full != self._root:
            raise PermissionError("Path escapes share root")
        return full

    def list_folder(self, path: str) -> List[paramiko.SFTPAttributes]:
        target = self._resolve(path)
        files = []
        for entry in target.iterdir():
            attr = paramiko.SFTPAttributes.from_stat(entry.stat())
            attr.filename = entry.name
            files.append(attr)
        return files

    def stat(self, path: str) -> paramiko.SFTPAttributes:
        return paramiko.SFTPAttributes.from_stat(self._resolve(path).stat())

    def lstat(self, path: str) -> paramiko.SFTPAttributes:
        return paramiko.SFTPAttributes.from_stat(self._resolve(path).lstat())

    def open(self, path: str, flags: int, attr):  # type: ignore[no-untyped-def]
        target = self._resolve(path)
        flags_os = flags
        mode = getattr(attr, "st_mode", 0o644) if attr else 0o644
        if flags_os & os.O_CREAT:
            target.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(target, flags_os, mode)
        if flags_os & os.O_RDWR:
            file_mode = "r+b"
        elif flags_os & os.O_WRONLY:
            file_mode = "wb"
        else:
            file_mode = "rb"
        fobj = os.fdopen(fd, file_mode)
        handle = paramiko.SFTPHandle(flags)
        handle.readfile = fobj
        handle.writefile = fobj
        return handle

    def remove(self, path: str) -> int:
        self._resolve(path).unlink()
        return paramiko.SFTP_OK

    def rename(self, oldpath: str, newpath: str) -> int:
        self._resolve(oldpath).rename(self._resolve(newpath))
        return paramiko.SFTP_OK

    def mkdir(self, path: str, attr) -> int:  # type: ignore[no-untyped-def]
        self._resolve(path).mkdir(parents=True, exist_ok=True)
        return paramiko.SFTP_OK

    def rmdir(self, path: str) -> int:
        self._resolve(path).rmdir()
        return paramiko.SFTP_OK


class _FileShareSSHServer(paramiko.ServerInterface):
    def __init__(self, share_root: Path):
        self._share_root = share_root

    def check_channel_request(self, kind: str, chanid: int) -> int:
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def get_allowed_auths(self, username: str) -> str:
        return "password,publickey"

    def check_auth_password(self, username: str, password: str) -> int:
        return paramiko.AUTH_SUCCESSFUL if user_store.verify_password(username, password) else paramiko.AUTH_FAILED

    def check_auth_publickey(self, username: str, key) -> int:  # type: ignore[no-untyped-def]
        keys = user_store.authorized_keys(username)
        if not keys:
            return paramiko.AUTH_FAILED
        for entry in keys:
            parsed = _parse_public_key(entry)
            if parsed and key == parsed:
                return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_channel_subsystem_request(self, channel, name: str) -> bool:  # type: ignore[no-untyped-def]
        if name == "sftp":
            return True
        return False

    def check_channel_exec_request(self, channel, command: bytes) -> bool:  # type: ignore[no-untyped-def]
        try:
            cmd = command.decode("utf-8")
        except UnicodeDecodeError:
            return False
        if cmd.startswith("scp "):
            thread = threading.Thread(target=_handle_scp, args=(channel, cmd, self._share_root), daemon=True)
            thread.start()
            return True
        return False


def _handle_scp(channel, command: str, share_root: Path) -> None:  # type: ignore[no-untyped-def]
    parts = command.split()
    if "-t" in parts:
        _scp_sink(channel, _resolve_scp_path(parts[-1], share_root), share_root)
    elif "-f" in parts:
        _scp_source(channel, _resolve_scp_path(parts[-1], share_root))
    channel.close()


def _resolve_scp_path(path: str, share_root: Path) -> Path:
    rel = Path(path.lstrip("/"))
    full = (share_root / rel).resolve()
    if share_root not in full.parents and full != share_root:
        raise PermissionError("Path escapes share root")
    return full


def _scp_sink(channel, target: Path, share_root: Path) -> None:  # type: ignore[no-untyped-def]
    channel.sendall(b"\x00")
    if target.exists() and target.is_dir():
        base_dir = target
        forced_name = None
    else:
        base_dir = target.parent if target != share_root else share_root
        forced_name = target.name if target != share_root else None
    while True:
        line = _scp_readline(channel)
        if not line:
            break
        if line.startswith("C"):
            mode, size, filename = _parse_scp_header(line)
            if forced_name:
                filename = forced_name
            if not filename:
                _scp_error(channel, "Invalid filename")
                return
            dest_rel = (base_dir / filename).relative_to(share_root)
            dest = _resolve_scp_path(dest_rel.as_posix(), share_root)
            channel.sendall(b"\x00")
            _scp_receive_file(channel, dest, size, mode)
            channel.sendall(b"\x00")
        elif line.startswith("E"):
            channel.sendall(b"\x00")
            break
        else:
            _scp_error(channel, "Unsupported SCP command")
            return


def _scp_source(channel, path: Path) -> None:  # type: ignore[no-untyped-def]
    if not path.exists() or not path.is_file():
        _scp_error(channel, "File not found")
        return
    channel.sendall(b"\x00")
    size = path.stat().st_size
    header = f"C0644 {size} {path.name}\n".encode("utf-8")
    channel.sendall(header)
    _scp_expect_ack(channel)
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(32768)
            if not chunk:
                break
            channel.sendall(chunk)
    channel.sendall(b"\x00")
    _scp_expect_ack(channel)


def _parse_scp_header(line: str) -> tuple[int, int, str]:
    try:
        parts = line.split()
        mode = int(parts[0][1:], 8)
        size = int(parts[1])
        filename = parts[2]
        return mode, size, filename
    except Exception:
        return 0o644, 0, ""


def _scp_receive_file(channel, dest: Path, size: int, mode: int) -> None:  # type: ignore[no-untyped-def]
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as handle:
        remaining = size
        while remaining > 0:
            chunk = channel.recv(min(32768, remaining))
            if not chunk:
                break
            handle.write(chunk)
            remaining -= len(chunk)
    try:
        os.chmod(dest, mode)
    except OSError:
        pass
    _scp_expect_ack(channel)


def _scp_readline(channel) -> str:  # type: ignore[no-untyped-def]
    data = b""
    while not data.endswith(b"\n"):
        chunk = channel.recv(1)
        if not chunk:
            break
        data += chunk
    return data.decode("utf-8", errors="ignore").strip()


def _scp_expect_ack(channel) -> None:  # type: ignore[no-untyped-def]
    _ = channel.recv(1)


def _scp_error(channel, message: str) -> None:  # type: ignore[no-untyped-def]
    channel.sendall(b"\x01" + message.encode("utf-8") + b"\n")


def _parse_public_key(line: str) -> Optional[paramiko.PKey]:
    try:
        parts = line.strip().split()
        if len(parts) < 2:
            return None
        key_type, key_b64 = parts[0], parts[1]
        data = paramiko.py3compat.decodebytes(key_b64.encode("ascii"))
        if key_type == "ssh-rsa":
            return paramiko.RSAKey(data=data)
        if key_type == "ssh-ed25519":
            return paramiko.Ed25519Key(data=data)
        if key_type.startswith("ecdsa-"):
            return paramiko.ECDSAKey(data=data)
    except Exception:
        return None
    return None


@dataclass
class SFTPService:
    host_key: paramiko.PKey
    share_root: Path
    bind_addresses: List[str]
    port: int
    sockets: List[socket.socket] = field(default_factory=list)
    threads: List[threading.Thread] = field(default_factory=list)
    stop_event: threading.Event = field(default_factory=threading.Event)

    @property
    def is_running(self) -> bool:
        return any(thread.is_alive() for thread in self.threads)

    @classmethod
    def from_config(cls, config: Dict[str, object]) -> "SFTPService":
        share_root = Path(str(config["share_path"]))
        host_key = _load_host_key()
        bind_addresses = config.get("sftp_bind_addresses") or ["0.0.0.0"]
        if not isinstance(bind_addresses, list):
            bind_addresses = [str(bind_addresses)]
        port = int(config.get("sftp_port") or 2222)
        return cls(host_key=host_key, share_root=share_root, bind_addresses=bind_addresses, port=port)

    def start(self) -> None:
        for address in self.bind_addresses:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((address, self.port))
            sock.listen(100)
            self.sockets.append(sock)
            thread = threading.Thread(target=self._accept_loop, args=(sock,), daemon=True)
            self.threads.append(thread)
            thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        for sock in self.sockets:
            try:
                sock.close()
            except OSError:
                pass
        for thread in self.threads:
            thread.join(timeout=1)

    def _accept_loop(self, sock: socket.socket) -> None:
        while not self.stop_event.is_set():
            try:
                client, _ = sock.accept()
            except OSError:
                break
            thread = threading.Thread(target=self._handle_client, args=(client,), daemon=True)
            thread.start()

    def _handle_client(self, client: socket.socket) -> None:
        transport = paramiko.Transport(client)
        transport.add_server_key(self.host_key)
        server = _FileShareSSHServer(self.share_root)
        try:
            transport.set_subsystem_handler("sftp", paramiko.SFTPServer, _SFTPServer, self.share_root)
            transport.start_server(server=server)
            channel = transport.accept(20)
            if channel is None:
                transport.close()
                return
            while transport.is_active():
                time.sleep(0.5)
        except Exception:
            transport.close()
