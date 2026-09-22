# pyhome

A small smart home system written in Python: one server, many clients, and a web
dashboard. The server accepts client connections over TCP, keeps track of who is
online, and serves a dashboard. Clients and the server exchange messages in both
directions.

Both sides run as a console application with their own command prompt.

**Status:** server and client `1.0`, see [Known limitations](#known-limitations).

## Requirements

- Python 3.9 or newer
- `fastapi` and `uvicorn`, for the server. The client needs nothing beyond the
  standard library.

```
py -m pip install -r requirements.txt
```

## Running

On Windows, double click `launcher.pyw`. It lists the server and every client
config in `client/data/`. Tick what you want and press **Run**. Every app opens
in its own console, the launcher shows which are running and stops them one by
one or all at once. Stopping ends the process, the server sees that as an
ordinary dropped connection.

Or start them separately, each in its own console:

```
cd server && start.bat
cd client && start.bat
```

A client can use another config file, which is how one checkout runs several
clients:

```
py app.py --config data/kitchen.json
```

A new config file only needs `NAME`, the network settings and, for a device, `DEVICE`. If `ID` is
missing or empty, the first run generates one (8 hex characters) and writes it
back into the file. When making a new config by copying an existing one,
delete its `ID` line (or leave it empty) so the first run gives it a fresh
one; the launcher refuses configs that share an ID.

To keep strangers out, put the same `TOKEN` in the server's config and in every
client's config. A client with a missing or different token is refused with the
reason, and it stops retrying until you fix its config and type `reconnect`.

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
│   ├── web/index.html            dashboard page, renders itself from /api/clients
│   └── handlers/
│       ├── server_handler.py     opens the TCP listener
│       ├── client_handler.py     one coroutine per connected client
│       ├── web_handler.py        FastAPI dashboard
│       └── commands/             server only commands
├── client/
│   ├── app.py                    entry point
│   ├── devices/                  one package per kind of device (light, thermostat)
│   ├── data/config.json          client identity and which server to reach
│   └── handlers/
│       ├── connection_handler.py connects and reconnects, holds the socket
│       ├── message_handler.py    receives messages from the server
│       ├── device_handler.py     loads the device and runs its actions
│       └── commands/             client only commands
├── tests/                        plain scripts, run all with py tests/run_all.py
└── launcher.pyw                  GUI that starts and stops the server and clients
```

Server and client keep only what is genuinely their own. Everything that was the
same on both sides lives in `shared/`.

## Configuration

Both sides read `data/config.json`, or the file given with `--config`:

| Key | Description |
| --- | --- |
| `ID` | identifier, sent during the handshake, generated on first run when empty |
| `NAME` | display name |
| `TYPE` | `server` or `client`, sent as `role` in the handshake |
| `DEVICE` | client only, which device package to load from `client/devices/`, empty for none |
| `VERSION` | version string, shown in the window title |
| `HOST` | server: address to bind to. client: address to connect to |
| `PORT` | TCP port, `50000` by default |
| `TOKEN` | shared secret, the client sends it in `hello`. On the server, empty means every client is accepted, with a warning at startup |
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
| `do <id> <action> [key=value ...]` | | Runs a device action on a client and prints the result |
| `help` | `commands`, `?` | Lists all available commands |
| `list` | `ls` | Lists all clients, online ones in green |
| `send <id\|all> <message>` | `msg` | Sends a message to one client or to all |
| `shutdown` | `exit`, `quit` | Shuts down the server |
| `state <id>` | | Asks a client for its device state |

**Client**

| Command | Aliases | Description |
| --- | --- | --- |
| `about` | `self`, `info` | Information about the application |
| `clear` | `cls` | Clears the console |
| `disconnect` | `dc` | Disconnect from server |
| `help` | `commands`, `?` | Lists all available commands |
| `reconnect` | `rc` | Reconnect to server, re-reading the config first |
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

### Adding a device

A device is a package in `client/devices/<name>/`. The config's `DEVICE` names
the folder. Its `__init__.py` declares module level names, the same way a
command does:

```python
device = "light"
description = "Dimmable light"

async def turn_on(**params):
    ...

async def set_brightness(level=100, **params):
    ...

async def get_state():               # always available, returns a dict
    return {"on": True, "brightness": 80}

actions = [turn_on, set_brightness]  # what the server may ask for
```

The capabilities sent to the server are the names of the functions in
`actions`. An action that raises is reported back as a failed result, the
connection stays up.

## Web dashboard

The server runs FastAPI on port `50001`:

| Route | Description |
| --- | --- |
| `GET /` | the dashboard page (`server/web/index.html`), one card per connected client with its device, capabilities and last state, refreshed every 2 s |
| `GET /api/clients` | the connected clients as JSON, which the page reads |

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
| `hello` | client to server | `id`, `name`, `role`, `version`, `device`, `capabilities`, `token` |
| `welcome` | server to client | `id`, `name`, `role`, `version`, `host`, `port` |
| `denied` | server to client | `reason`, the server closes the connection after it |
| `msg` | both ways | `text` |
| `cmd` | server to client | `action`, `params`, `request_id` |
| `result` | client to server | `request_id`, `ok`, `state` or `error` |
| `state` | client to server | `state`, sent unprompted, once after connecting |

A connection goes:

1. The client opens a connection to `HOST:PORT`.
2. The client sends `hello`.
3. The server answers with `welcome`, or with `denied` and closes when it has a `TOKEN` and the client's does not match.
4. Both sides exchange messages until one of them closes the connection. The
   server may send `cmd` at any time and the client answers each with a
   `result` carrying the same `request_id`, so several commands can be in
   flight at once.

`type` is the envelope field, so a payload field never uses that name. The
config's `TYPE` travels as `role`.

The server stores every client it has seen in `clients.json` next to its
config file. Device state is kept in memory only.

## Tests

Plain scripts with asserts, no framework needed:

```
py tests/run_all.py
```

## Known limitations

- **The token is not encryption.** It travels in plain text over a plain TCP
  socket. It keeps a neighbour or a stray device on the same network out, it
  does not stop anyone who can watch the traffic.
- **The dashboard needs no token.** It is read only, but anyone who can reach
  its port sees every connected device and its state.
- **Clients are not addressable by name.** `send` takes an id or `all`.

## Roadmap

1. ~~A typed, newline framed message protocol shared by both sides~~
2. ~~Server to client messaging, addressed by client id~~
3. ~~Per instance configuration so one checkout can run several clients~~
4. ~~Device modules, so a client can declare what it is and what it can do~~
5. ~~Authentication during the handshake~~

Items 3 to 5 are v1.0 and are specified in
[docs/v1.0-spec.md](docs/v1.0-spec.md).
