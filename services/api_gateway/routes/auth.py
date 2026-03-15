"""Auth routes: login and require_admin dependency."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from starlette.responses import JSONResponse

from lib.audit import audit_log
from services.api_gateway.limiter import limiter
from services.auth_service import manager as auth_manager

auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginBody(BaseModel):
    password: str


@auth_router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, body: LoginBody):
    ip = request.client.host if request.client else ""
    if auth_manager.is_locked_out(ip):
        return JSONResponse(
            status_code=429,
            content={"error": "too many failed attempts, try again later"},
        )
    if auth_manager.validate_admin_password(body.password or ""):
        auth_manager.clear_lockout(ip)
        token = auth_manager.create_token()
        audit_log({"event": "login_success", "source_ip": ip})
        return {"token": token, "expires_in": 14400}
    locked = auth_manager.record_failed_attempt(ip)
    audit_log({"event": "login_failure", "source_ip": ip, "locked_out": locked})
    return JSONResponse(status_code=401, content={"error": "invalid password"})


async def require_admin(request: Request) -> str:
    auth = request.headers.get("Authorization")
    token = None
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ", 1)[-1].strip()
    if not token or not auth_manager.verify_token(token):
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    ip = request.client.host if request.client else ""
    audit_log({"event": "admin_action", "source_ip": ip, "path": str(request.url.path)})
    return token
