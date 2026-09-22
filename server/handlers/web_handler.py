from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from handlers.client_handler import get_connected_clients

app = FastAPI(title="Server Dashboard")

# the page is static and renders itself from /api/clients
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


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


@app.get("/", response_class=FileResponse)
async def home():
    return FileResponse(WEB_DIR / "index.html", media_type="text/html")


@app.get("/api/clients")
async def api_clients():
    return {"clients": serialize_clients()}
