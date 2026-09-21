from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from handlers.client_handler import get_connected_clients

app = FastAPI(title="Server Dashboard")


def serialize_clients():
    """Client list without the writer objects, which cannot be turned into JSON."""
    clients = []
    for addr, info in get_connected_clients().items():
        clients.append({
            "id": info.get("id"),
            "name": info.get("name"),
            "host": addr[0],
            "port": addr[1],
        })
    return clients


@app.get("/", response_class=HTMLResponse)
async def home():
    clients = serialize_clients()

    html = "<h1>Aktívni klienti</h1>"
    if not clients:
        return html + "<p>Žiadny pripojený klient.</p>"

    html += "<ul>"
    for client in clients:
        html += f"<li>{client['name']}#{client['id']} — {client['host']}:{client['port']}</li>"
    html += "</ul>"
    return html


@app.get("/api/clients")
async def api_clients():
    return {"clients": serialize_clients()}
