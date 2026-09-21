# pyhome

A small smart home system written in Python: one server, many clients, and a web
dashboard. The server accepts client connections over TCP, keeps track of who is
online, and serves a dashboard. Clients and the server exchange messages in both
directions.

Both sides run as a console application with their own command prompt.

**Status:** server and client `0.9`, see [Known limitations](#known-limitations).

## Requirements

- Python 3.9 or newer
- `fastapi` and `uvicorn`, for the server. The client needs nothing beyond the
  standard library.

```
py -m pip install -r requirements.txt
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

The server listens on TCP port `50000` for clients and prints the dashboard
address on startup, including the one other devices on the network can use:

```
Server#1 running on 0.0.0.0:50000
Dashboard running on http://localhost:50001
                     http://192.168.1.20:50001
```

## Project structure

```
pyhome/
├── shared/                       code both sides use
│   ├── protocol.py               message framing and message types
│   ├── command_handler.py        loads commands, reads the console prompt
│   ├── config.py                 read and write data/config.json
│   ├── console.py                printing that redraws the prompt
│   ├── colors.py                 ANSI colors
│   ├── symbols.py                status symbols
│   ├── network.py                local address and reachability
│   └── commands/                 commands both sides have
├── server/
│   ├── app.py                    entry point, runs all handlers with asyncio.gather
│   ├── data/
│   │   ├── config.json           server identity and network settings
│   │   └── clients.json          every client seen so far, created at runtime
│   └── handlers/
│       ├── server_handler.py     opens the TCP listener
│       ├── client_handler.py     one coroutine per connected client
│       ├── web_handler.py        FastAPI dashboard
│       └── commands/             server only commands
├── client/
│   ├── app.py                    entry point
│   ├── data/config.json          client identity and which server to reach
│   └── handlers/
│       ├── connection_handler.py connects and reconnects, holds the socket
│       ├── message_handler.py    receives messages from the server
│       └── commands/             client only commands
└── start_all.bat
```

Server and client keep only what is genuinely their own. Everything that was the
same on both sides lives in `shared/`.

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
| `WEB_HOST` | server only, address the dashboard binds to |
| `WEB_PORT` | server only, dashboard port, `50001` by default |

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
| `send <id\|all> <message>` | `msg` | Sends a message to one client or to all |
| `shutdown` | `exit`, `quit` | Shuts down the server |

**Client**

| Command | Aliases | Description |
| --- | --- | --- |
| `about` | `self`, `info` | Information about the application |
| `clear` | `cls` | Clears the console |
| `disconnect` | `dc` | Disconnect from server |
| `help` | `commands`, `?` | Lists all available commands |
| `reconnect` | `rc` | Reconnect to server |
| `send [message]` | `msg` | Send message to server, asks for it if omitted |
| `shutdown` | `exit`, `quit` | Shuts down the application |

### Adding a command

Commands are loaded automatically from `shared/commands/` first and then from the
side's own `handlers/commands/`. Drop in a new file and it shows up at the prompt
and in `help`, no registration needed. A later folder wins, so a side can replace
a shared command with its own version.

A command module declares three things:

```python
command = ["mycommand", "mc"]        # first name is canonical, the rest are aliases
description = "What the command does"

async def function(*params):         # may also be a plain def, params are optional
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

TCP is a stream of bytes rather than of messages, so two messages sent in quick
succession can arrive merged and a long one can arrive split. Every message is
therefore a single line of UTF-8 JSON terminated by `\n`, and each side reads
exactly one line at a time.

Every message is an object with a `type` field. The rest of the fields depend on
the type. A message of an unknown type is reported and ignored, so new types can
be added without breaking peers that do not know them yet.

| Type | Direction | Fields |
| --- | --- | --- |
| `hello` | client to server | `id`, `name`, `device_type`, `version` |
| `welcome` | server to client | `id`, `name`, `device_type`, `version`, `host`, `port` |
| `msg` | both ways | `text` |

A connection goes:

1. The client opens a connection to `HOST:PORT`.
2. The client sends `hello`.
3. The server answers with `welcome`.
4. Both sides exchange `msg` until one of them closes the connection.

`type` is the envelope field, so a payload field never uses that name. The kind
of device travels as `device_type`.

The server stores every client it has seen in `data/clients.json`.

## Known limitations

- **One identity per checkout.** `ID` is fixed in `data/config.json`, so running
  several clients means several copies of the folder.
- **No authentication.** The TCP listener and the dashboard both bind to
  `0.0.0.0` and accept anyone who can reach them.
- **Clients are not addressable by name.** `send` takes an id or `all`.

## Roadmap

1. ~~A typed, newline framed message protocol shared by both sides~~
2. ~~Server to client messaging, addressed by client id~~
3. Per instance configuration so one checkout can run several clients
4. Device modules, so a client can declare what it is and what it can do
5. Authentication during the handshake

Items 3 to 5 are v1.0 and are specified in
[docs/v1.0-spec.md](docs/v1.0-spec.md).
