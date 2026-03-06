# Phase 2 Route Migration — Consolidated Review

**Date:** 2026-03-06  
**Scope:** All Phase 2 route file migrations (Prompts 4A–4F)  
**Reviewer:** chibashr (reviewing subagent)

---

## Verdict: **BLOCKED**

One blocker must be fixed before Phase 3 starts.

---

## Consistency Check

| Check | Status | Notes |
|-------|--------|-------|
| All routers use APIRouter pattern | ✅ PASS | system, network, serial, capture, updates, backup, logs, modules, remote all use `APIRouter(prefix="...", tags=[...])` |
| All routers use success_response() wrapper | ✅ PASS | All migrated routes use `success_response()` from `..response` |
| Path parameter syntax: `{id}` not `<id>` | ✅ PASS | All path params use FastAPI `{id}` style (e.g. `{capture_id}`, `{interface_id}`) |
| All routers imported and registered in main | ✅ PASS | 9 routers in `__init__.py`; dashboard uses stub |

---

## Async Consistency

| Check | Status | Notes |
|-------|--------|-------|
| No mixed sync/async within a single handler | ✅ PASS | Each handler is either sync or async; no mixing |
| Subprocess/blocking wrapped in executor | ✅ PASS | `serial.list_devices` → `asyncio.to_thread`; `serial.get_log_content` → `asyncio.to_thread`; `backup.restore_config` → `run_in_executor` |
| No Flask imports in route files | ❌ **BLOCKED** | `dashboard.py` still imports `from flask import Blueprint` |

---

## Response Format

| Check | Status | Notes |
|-------|--------|-------|
| success_response() envelope unchanged | ✅ PASS | `response.py` returns `{"data": ..., "meta": {"timestamp": ...}}` |
| FileResponse for download endpoints | ✅ PASS | capture, backup, logs, serial all use FileResponse correctly |
| Error responses use appropriate HTTP status | ✅ PASS | 400, 404, 500 used via `error_response(..., status_code=...)` |

---

## Cross-Route Issues

| Check | Status | Notes |
|-------|--------|-------|
| No route path collisions | ✅ PASS | No overlapping paths between routers |
| No duplicate prefix definitions | ✅ PASS | Each router defines prefix once; `__init__` includes without extra prefix |
| Dashboard blueprint migrated | ❌ **BLOCKED** | Dashboard still Flask; served by stub (501) |

---

## Blocker: Dashboard Not Migrated

**File:** `services/api_gateway/routes/dashboard.py`

**Issue:** Dashboard was not migrated to FastAPI. It still uses:
- `from flask import Blueprint`
- `dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/v1/dashboard")`
- `@dashboard_bp.get("/status")`

**Current behavior:** `__init__.py` registers a **stub** for `/api/v1/dashboard` via `_stub_router()`, so all dashboard requests return 501. The real `dashboard.py` is never used.

**Required fix:** Migrate `dashboard.py` to FastAPI:
1. Replace `Blueprint` with `APIRouter`
2. Replace `@dashboard_bp.get` with `@router.get`
3. Import and register `dashboard_router` in `__init__.py` instead of the stub
4. Remove Flask imports

---

## Minor (Non-Blocking)

| Item | Severity | Details |
|------|----------|---------|
| FileResponse import source | Low | `serial.py` uses `starlette.responses.FileResponse`; others use `fastapi.responses.FileResponse`. Both work; consider standardizing on `fastapi.responses` for consistency. |
| Router variable naming | Low | `system` and `serial` use `router`; others use `{name}_router`. Aliased correctly in `__init__`; no functional impact. |

---

## Summary

| Category | Result |
|----------|--------|
| Consistency | PASS |
| Async | BLOCKED (Flask in dashboard.py) |
| Response format | PASS |
| Cross-route | BLOCKED (dashboard not migrated) |

**Action:** Implementer subagent should migrate `dashboard.py` to FastAPI and register it in `__init__.py` before Phase 3 (WebSocket handlers) begins.
