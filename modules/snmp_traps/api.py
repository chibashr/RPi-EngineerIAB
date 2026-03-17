from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from modules.snmp_trap_receiver import receiver

router = APIRouter()


def _get_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


@router.get("/status")
async def get_status() -> dict[str, Any]:
    return receiver.get_status()


@router.get("/recent")
async def get_recent(
    limit: int = Query(100, ge=0),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    items = receiver.get_recent(limit=limit, offset=offset)
    return {"items": items}


@router.get("/stored")
async def get_stored(
    limit: int = Query(100, ge=0),
    offset: int = Query(0, ge=0),
    source: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> dict[str, Any]:
    items = receiver.get_stored(
        limit=limit,
        offset=offset,
        source=source,
        since=since,
        until=until,
    )
    return {"items": items}


@router.get("/config")
async def get_config() -> dict[str, Any]:
    return receiver.load_config()


@router.put("/config")
async def update_config(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    data = payload or {}
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid configuration payload")
    receiver.apply_config(data)
    return receiver.load_config()


@router.post("/clear")
async def clear(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    data = payload or {}
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid clear payload")
    target = str(data.get("target", "live"))
    if target not in {"live", "stored", "all"}:
        raise HTTPException(status_code=400, detail="Invalid clear target")
    if target in {"live", "all"}:
        receiver.clear_recent()
    if target in {"stored", "all"}:
        receiver.clear_stored()
    return {"cleared": target}


@router.post("/start")
async def start() -> dict[str, Any]:
    config = receiver.load_config()
    config["enabled"] = True
    receiver.save_config(config)
    receiver.start_receiver()
    return receiver.get_status()


@router.post("/stop")
async def stop() -> dict[str, Any]:
    receiver.stop_receiver()
    config = receiver.load_config()
    config["enabled"] = False
    receiver.save_config(config)
    return receiver.get_status()


@router.post("/restart")
async def restart() -> dict[str, Any]:
    receiver.stop_receiver()
    config = receiver.load_config()
    config["enabled"] = True
    receiver.save_config(config)
    receiver.start_receiver()
    return receiver.get_status()


@router.get("/storage")
async def get_storage() -> dict[str, Any]:
    return receiver.get_storage_info()
