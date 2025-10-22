from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from handlers.client_handler import get_connected_clients

app = FastAPI(title="Server Dashboard")

@app.get("/", response_class=HTMLResponse)
async def home():
    clients = get_connected_clients()
    html = "<h1>Aktívni klienti</h1><ul>"
    for client in clients:
        html += f"<li>{client}</li>"
    html += "</ul>"
    return html

@app.get("/api/clients")
async def api_clients():
    return {"clients": get_connected_clients}
