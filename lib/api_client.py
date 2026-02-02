"""Internal API client for service-to-service calls."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
from urllib import error as url_error
from urllib import parse as url_parse
from urllib import request as url_request

DEFAULT_API_BASE = os.getenv("RPI_ENGINEER_API_BASE", "http://127.0.0.1:5000")
DEFAULT_TIMEOUT = 10


def get(path: str, params: Optional[Dict[str, object]] = None, base_url: str = DEFAULT_API_BASE):
    return _request("GET", path, params=params, base_url=base_url)


def post(
    path: str,
    payload: Optional[Dict[str, object]] = None,
    base_url: str = DEFAULT_API_BASE,
):
    return _request("POST", path, json_body=payload, base_url=base_url)


def put(
    path: str,
    payload: Optional[Dict[str, object]] = None,
    base_url: str = DEFAULT_API_BASE,
):
    return _request("PUT", path, json_body=payload, base_url=base_url)


def delete(
    path: str,
    payload: Optional[Dict[str, object]] = None,
    base_url: str = DEFAULT_API_BASE,
):
    return _request("DELETE", path, json_body=payload, base_url=base_url)


def _request(
    method: str,
    path: str,
    *,
    params: Optional[Dict[str, object]] = None,
    json_body: Optional[Dict[str, object]] = None,
    base_url: str = DEFAULT_API_BASE,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    url = _build_url(base_url, path, params)
    data = None
    headers = {"Accept": "application/json"}
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = url_request.Request(url, data=data, headers=headers, method=method)
    try:
        with url_request.urlopen(request, timeout=timeout) as response:
            return _parse_response(response)
    except url_error.HTTPError as exc:
        payload = exc.read()
        message = _decode_error(payload, exc.headers.get("Content-Type", ""))
        raise RuntimeError(f"{method} {url} failed with {exc.code}: {message}") from exc
    except url_error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc


def _build_url(base_url: str, path: str, params: Optional[Dict[str, object]]) -> str:
    base = base_url.rstrip("/")
    safe_path = path if path.startswith("/") else f"/{path}"
    url = f"{base}{safe_path}"
    if params:
        url = f"{url}?{url_parse.urlencode(params, doseq=True)}"
    return url


def _parse_response(response: url_request.addinfourl) -> Dict[str, Any]:
    content_type = response.headers.get("Content-Type", "")
    raw = response.read()
    if not raw:
        return {"status": response.status, "data": None}
    if "application/json" in content_type:
        return {"status": response.status, "data": json.loads(raw.decode("utf-8"))}
    text = raw.decode("utf-8", errors="ignore")
    return {"status": response.status, "data": text}


def _decode_error(payload: bytes, content_type: str) -> str:
    if not payload:
        return "No response body"
    if "application/json" in content_type:
        try:
            parsed = json.loads(payload.decode("utf-8"))
            return json.dumps(parsed)
        except json.JSONDecodeError:
            return payload.decode("utf-8", errors="ignore")
    return payload.decode("utf-8", errors="ignore")
