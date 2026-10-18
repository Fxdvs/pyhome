from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from handlers.client_handler import get_connected_clients, token_matches, token_required

app = FastAPI(title="Server Dashboard")

# the page is static and renders itself from /api/clients
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def bearer_token(authorization):
    """The token from an 'Authorization: Bearer <token>' header, or None."""
    if not isinstance(authorization, str):
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return token.strip() or None


async def require_token(authorization=Header(default=None)):
    """401 unless the request carries the server's TOKEN. Lets everything through when there is none."""
    if not token_required():
        return
    if not token_matches(bearer_token(authorization)):
        raise HTTPException(status_code=401, detail="token required", headers={"WWW-Authenticate": "Bearer"})


def dashboard_warning():
    """The startup warning for a dashboard anyone can read, or None."""
    if token_required():
        return None
    return "No TOKEN set, anyone who can reach the dashboard sees every device"


# one shape for every error, {"error": ...}, the page reads only that
@app.exception_handler(StarletteHTTPException)
async def error_body(request, exc):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code, headers=exc.headers)


def serialize_clients():
    """Client list without the writer objects, which cannot be turned into JSON."""
    clients = []
    for addr, info in get_connected_clients().items():
        clients.append({
            "id": info.get("id"),
            "name": info.get("name"),
            "host": addr[0],
            "port": addr[1],
            "device": info.get("device"),
            "capabilities": info.get("capabilities", []),
            "last_state": info.get("last_state"),
        })
    return clients


# the page holds no data, it has to load without a token to be able to ask for one
@app.get("/", response_class=FileResponse)
async def home():
    return FileResponse(WEB_DIR / "index.html", media_type="text/html")


# no token needed, the page asks here whether it has to show the prompt
@app.get("/api/status")
async def api_status():
    return {"token_required": token_required()}


@app.get("/api/clients", dependencies=[Depends(require_token)])
async def api_clients():
    return {"clients": serialize_clients()}
