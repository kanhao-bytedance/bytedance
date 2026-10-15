"""Single-workspace access gate for a small hosted MVP."""
import base64
import binascii
import secrets
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse

from .settings import settings


class DashboardAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if not settings.dashboard_password or scope["path"] == "/health":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        username = password = ""
        try:
            scheme, value = headers.get("authorization", "").split(" ", 1)
            if scheme.lower() == "basic":
                username, password = base64.b64decode(value, validate=True).decode("utf-8").split(":", 1)
        except (ValueError, UnicodeError, binascii.Error):
            pass
        user_matches = secrets.compare_digest(username.encode(), settings.dashboard_user.encode())
        password_matches = secrets.compare_digest(password.encode(), settings.dashboard_password.encode())
        if not (user_matches and password_matches):
            response = JSONResponse({"detail": "Sign in to access this workspace."}, 401,
                                    headers={"WWW-Authenticate": 'Basic realm="Signal", charset="UTF-8"',
                                             "Cache-Control": "no-store"})
            await response(scope, receive, send)
            return
        # Browsers send Basic credentials automatically. Reject cross-origin writes.
        origin = headers.get("origin")
        if scope["method"] not in {"GET", "HEAD", "OPTIONS"} and origin:
            try:
                parsed = urlsplit(origin)
            except ValueError:
                parsed = urlsplit("invalid:")
            if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != headers.get("host", "").lower():
                response = JSONResponse({"detail": "Cross-origin writes are not allowed."}, 403)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
