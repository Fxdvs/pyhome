import asyncio
import json
import math
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from shared.colors import GRAY, RESET
from shared.console import print_message
from handlers.client_handler import (
    COMMAND_TIMEOUT,
    get_connected_clients,
    printable,
    send_command,
    token_matches,
    token_required,
)

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


async def require_controls():
    """403 on a server without a TOKEN: an open dashboard may look, never switch anything."""
    if not token_required():
        raise HTTPException(status_code=403, detail="set TOKEN on the server to control devices from the browser")


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


def parse_do_body(body):
    """(action, params) from a do request body. ValueError with the reason when it is not one."""
    if not isinstance(body, dict):
        raise ValueError("body must be a JSON object")

    action = body.get("action")
    if not isinstance(action, str) or not action:
        raise ValueError("action must be a non-empty string")

    params = body.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    # flat values only, the same the console's key=value can produce
    for key, value in params.items():
        if not isinstance(value, (bool, int, float, str)):
            raise ValueError(f"params.{key} must be true, false, a number or text")
        # json.loads lets NaN and Infinity through, no device means them
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"params.{key} must be a finite number")
    return action, params


async def dashboard_do(client_id, body, source, timeout=COMMAND_TIMEOUT):
    """Run a device action asked for from the browser. Returns (status, response body)."""
    try:
        action, params = parse_do_body(body)
    except ValueError as e:
        return 400, {"error": str(e)}

    info = next((i for i in get_connected_clients().values() if i["id"] == client_id), None)
    if info is None:
        return 404, {"error": f"no online client with id '{client_id}'"}

    # whoever runs the server sees what the house is doing, and from where
    print_message(f"{GRAY}Dashboard {printable(source)} → {printable(info['name'])}#{printable(client_id)} "
                  f"{printable(action)} {printable(json.dumps(params, ensure_ascii=False), 120)}{RESET}")

    try:
        result = await send_command(client_id, action, params, timeout)
    except LookupError as e:
        # it went offline between the check above and the send
        return 404, {"error": str(e)}
    except ValueError as e:
        return 400, {"error": str(e)}
    except asyncio.TimeoutError:
        # before OSError: from python 3.11 on a TimeoutError is an OSError too
        return 504, {"error": f"no answer within {timeout:g} s"}
    except OSError:
        return 502, {"error": "client disconnected"}

    # the device answered, a refused value is its answer, not a failed request
    if result.get("ok") is True:
        return 200, {"ok": True, "state": result.get("state")}
    return 200, {"ok": False, "error": str(result.get("error") or "the device refused")}


# no token needed, the page asks here whether it has to show the prompt and the controls
@app.get("/api/status")
async def api_status():
    required = token_required()
    return {"token_required": required, "controls": required}


@app.get("/api/clients", dependencies=[Depends(require_token)])
async def api_clients():
    return {"clients": serialize_clients()}


# the annotation is how FastAPI hands over the raw request, the body is checked by hand
@app.post("/api/clients/{client_id}/do", dependencies=[Depends(require_token), Depends(require_controls)])
async def api_do(client_id, request: Request):
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse({"error": "body must be JSON"}, status_code=400)
    source = request.client.host if request.client else "?"
    status, answer = await dashboard_do(client_id, body, source)
    return JSONResponse(answer, status_code=status)
