# pyhome

A small smart home system written in Python: one server, many clients, and a web
dashboard. The server accepts client connections over TCP, keeps track of who is
online, and serves a dashboard. Each client connects, identifies itself, and can
exchange messages with the server.

Both sides run as a console application with their own command prompt.

**Status:** server `0.8`, client `0.7`. Early base version, see
[Known limitations](#known-limitations).

## Requirements

- Python 3.9 or newer
- `fastapi` and `uvicorn` (server only)

```
py -m pip install fastapi uvicorn
```

## Running

On Windows, start both at once:

```
start_all.bat
```

Or start them separately, each in its own console:

```
cd server && start.bat
cd client && start.bat
```

The server listens on TCP port `50000` for clients and serves the dashboard on
`http://localhost:50001`.

## Project structure

```
pyhome/
├── server/
│   ├── app.py                    entry point, runs all handlers with asyncio.gather
│   ├── data/
│   │   ├── config.json           server identity and network settings
│   │   └── clients.json          every client that has ever connected
│   ├── handlers/
│   │   ├── server_handler.py     opens the TCP listener
│   │   ├── client_handler.py     one coroutine per connected client
│   │   ├── command_handler.py    loads commands, reads the console prompt
│   │   ├── web_handler.py        FastAPI dashboard
│   │   └── commands/             one file per command
│   └── utils/
│       ├── config.py             read and write data/config.json
│       ├── console.py            thread safe printing that redraws the prompt
│       ├── colors.py             ANSI colors
│       ├── symbols.py            status symbols
│       └── network.py            internet reachability check
├── client/
│   ├── app.py                    entry point
│   ├── data/config.json          client identity and which server to reach
│   ├── handlers/
│   │   ├── connection_handler.py connects and reconnects, holds the socket
│   │   ├── message_handler.py    receives messages from the server
│   │   ├── command_handler.py    loads commands, reads the console prompt
│   │   └── commands/             one file per command
│   └── utils/                    same helpers as the server
└── start_all.bat
```

Server and client share the same layout on purpose. The `utils` packages are
currently copies of each other.

## Configuration

Both sides read `data/config.json`:

| Key | Description |
| --- | --- |
| `ID` | identifier, sent during the handshake |
| `NAME` | display name |
| `TYPE` | `server` or `client` |
| `VERSION` | version string, shown in the window title |
| `HOST` | server: address to bind to. client: address to connect to |
| `PORT` | TCP port, `50000` by default |

The server can rename itself at runtime with `data config edit name`.

## Commands

Type commands at the `>` prompt. Every command has aliases.

**Server**

| Command | Aliases | Description |
| --- | --- | --- |
| `about` | `self`, `info` | Information about the application |
| `clear` | `cls` | Clears the console |
| `data clients clear` | `data clients cls` | Clears the client list |
| `data config edit name` | `data conf edit name` | Edits the server name |
| `data config show` | `data conf show` | Shows formatted config.json |
| `help` | `commands`, `?` | Lists all available commands |
| `list` | `ls` | Lists all clients, online ones in green |
| `shutdown` | `exit`, `quit` | Shuts down the server |

**Client**

| Command | Aliases | Description |
| --- | --- | --- |
| `about` | `self`, `info` | Information about the application |
| `clear` | `cls` | Clears the console |
| `disconnect` | `dc` | Disconnect from server |
| `help` | `commands`, `?` | Lists all available commands |
| `reconnect` | `rc` | Reconnect to server |
| `send` | `msg` | Send message to server |
| `shutdown` | `exit`, `quit` | Shuts down the application |

### Adding a command

Commands are loaded automatically from `handlers/commands/`. Drop in a new file
and it shows up at the prompt and in `help`, no registration needed. A command
module declares three things:

```python
command = ["mycommand", "mc"]        # first name is canonical, the rest are aliases
description = "What the command does"

async def function():                # may also be a plain def
    ...
```

## Web dashboard

The server runs FastAPI on port `50001`:

| Route | Description |
| --- | --- |
| `GET /` | HTML page listing the currently connected clients |
| `GET /api/clients` | the same list as JSON |

## Protocol

Clients talk to the server over a plain TCP socket.

1. The client opens a connection to `HOST:PORT`.
2. The client sends its identity as UTF-8 JSON: `{"id": "1", "name": "Client"}`.
3. The server replies with its own details: `{"id", "name", "type", "version", "host", "port"}`.
4. From then on both sides exchange raw UTF-8 text.

The server stores every client it has seen in `data/clients.json` and prints
incoming messages to its console.

## Known limitations

This is the base version. The following are known and planned to be addressed:

- **No message framing.** TCP is a byte stream, so two messages sent in quick
  succession can arrive merged, and a long message can arrive split.
- **No server to client messaging.** The client can send to the server, not the
  other way around.
- **One identity per checkout.** `ID` is fixed in `data/config.json`, so running
  several clients means several copies of the folder.
- **No authentication.** The TCP listener and the dashboard both bind to
  `0.0.0.0` and accept anyone who can reach them.
- **Duplicated helpers.** `utils/` exists twice, once per side.

## Roadmap

1. A typed, newline framed message protocol shared by both sides
2. Server to client messaging, addressed by client id
3. Per instance configuration so one checkout can run several clients
4. Device modules, so a client can declare what it is and what it can do
5. Authentication during the handshake
