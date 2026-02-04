"""FTP server implementation for file share."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from . import user_store


_FTP_PERMS = "elradfmwMT"
_FTP_READONLY = "elr"


class _FileShareAuthorizer:
    def __init__(self, share_path: Path, anonymous_mode: str) -> None:
        self._share_path = share_path
        self._anonymous_mode = anonymous_mode

    def has_user(self, username: str) -> bool:
        if username == "anonymous":
            return self._anonymous_mode != "off"
        return any(user["username"] == username for user in user_store.list_users())

    def validate_authentication(self, username: str, password: str, handler) -> None:  # type: ignore[no-untyped-def]
        try:
            from pyftpdlib.authorizers import AuthenticationFailed
        except ImportError:  # pragma: no cover - dependency check
            AuthenticationFailed = RuntimeError
        if username == "anonymous":
            if self._anonymous_mode == "off":
                raise AuthenticationFailed("Anonymous access disabled")
            return
        if not user_store.verify_password(username, password):
            raise AuthenticationFailed("Invalid credentials")

    def get_home_dir(self, username: str) -> str:
        return str(self._share_path)

    def has_perm(self, username: str, perm: str, path: str = None) -> bool:  # type: ignore[no-untyped-def]
        if username == "anonymous":
            if self._anonymous_mode == "readwrite":
                return perm in _FTP_PERMS
            if self._anonymous_mode == "readonly":
                return perm in _FTP_READONLY
            return False
        return perm in _FTP_PERMS

    def get_perms(self, username: str) -> str:
        if username == "anonymous":
            return _FTP_PERMS if self._anonymous_mode == "readwrite" else _FTP_READONLY
        return _FTP_PERMS

    def get_msg_login(self, username: str) -> str:
        return "File share FTP ready."

    def get_msg_quit(self, username: str) -> str:
        return "Goodbye."


@dataclass
class FTPService:
    servers: List[object]
    threads: List[threading.Thread]

    @property
    def is_running(self) -> bool:
        return any(thread.is_alive() for thread in self.threads)

    @classmethod
    def from_config(cls, config: Dict[str, object]) -> "FTPService":
        try:
            from pyftpdlib.handlers import FTPHandler
            from pyftpdlib.servers import FTPServer
        except ImportError as exc:  # pragma: no cover - dependency check
            raise RuntimeError("pyftpdlib is required for FTP support") from exc

        share_path = Path(str(config["share_path"]))
        authorizer = _FileShareAuthorizer(share_path, str(config.get("ftp_anonymous", "off")))
        handler = FTPHandler
        handler.authorizer = authorizer
        handler.banner = "RPi Engineer File Share FTP"

        bind_addresses = config.get("ftp_bind_addresses") or ["0.0.0.0"]
        if isinstance(bind_addresses, list):
            addresses = [str(addr) for addr in bind_addresses]
        else:
            addresses = [str(bind_addresses)]
        port = int(config.get("ftp_port") or 2121)

        servers = []
        threads = []
        for address in addresses:
            server = FTPServer((address, port), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            servers.append(server)
            threads.append(thread)
        return cls(servers=servers, threads=threads)

    def start(self) -> None:
        for thread in self.threads:
            thread.start()

    def stop(self) -> None:
        for server in self.servers:
            try:
                server.close_all()
            except Exception:
                pass
        for thread in self.threads:
            thread.join(timeout=1)
