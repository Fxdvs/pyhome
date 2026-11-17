# The server in Docker

The server runs in a container: one command starts it, it starts again on
its own after a reboot or a crash, everything it knows is in one folder,
`server-data/`, and `docker compose stop` ends it cleanly. The clients and
the launcher stay where they are and reach it like any server.

Each step below shows what to type and what you should see. Commands are
typed in the folder of the checkout, in PowerShell on Windows or a terminal
on Linux.

## 1. Install Docker

**Windows 10 or 11:** install [Docker Desktop](https://www.docker.com/products/docker-desktop/),
keep the WSL 2 option it offers, restart when asked, and start Docker Desktop.
In its settings, **Start Docker Desktop when you sign in** keeps the server
running after a reboot.

**Raspberry Pi or another Linux machine:**

```
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

then log out and in again, so `docker` works without `sudo`.

Check it:

```
docker compose version
```

You should see `Docker Compose version v2.24` or newer.

## 2. Start the server

```
docker compose up -d --build
```

The first time this builds the image, about a minute. Then:

```
docker ps
```

shows `pyhome` with `Up ... (healthy)` after about 20 seconds. The server made
`server-data/config.json` from the example: open it and set at least:

- `NAME`, what the dashboard and clients show, e.g. `"Dom"`
- `TOKEN`, so only your clients get in. Make one with
  `py -c "import secrets; print(secrets.token_urlsafe(16))"`

Keep `HOST` and `WEB_HOST` at `0.0.0.0`. Then restart it:

```
docker compose restart
```

**The address your house uses.** Inside a container the server sees only
the container's own address. Tell it yours: find it with `ipconfig` (Windows,
`IPv4 Address`) or `hostname -I` (Linux), and put it in a file named `.env`
next to `docker-compose.yml`:

```
PYHOME_ADDRESS=192.168.1.20
```

then `docker compose up -d`. The dashboard line now shows
`http://192.168.1.20:50001`, and certificates made later name that address.
`.env` is ignored by git, so `git pull` never touches it.

**On Linux:** the container writes as uid 1000, the first user on a Pi. If
`docker compose logs` shows `Permission denied` for `/data`, give the folder
to that user once: `sudo chown -R 1000 server-data`.

## 3. The console and the logs

```
docker attach pyhome
```

is the server's console, the same commands as in its window (`list`,
`do kuch turn_on`, `history kuch`, `help`). **Leave it with Ctrl+P, then
Ctrl+Q.** Ctrl+C ends the server, and Docker starts it again at once
(`restart: unless-stopped`); to stop it, `docker compose stop`.

Only the output, without the console:

```
docker compose logs -f
```

## 4. Certificates and TLS

Make them inside the container, into `server-data/certs/`:

```
docker compose exec server python make_certs.py
```

The certificate names `localhost`, `pyhome` and your `PYHOME_ADDRESS`. Add
other names a phone may use with `--host dom.lan`. Note the line
`ca.crt is new, fingerprint ...`: that is how the authority is recognized.

Then in `server-data/config.json`:

```json
"TLS_CERT": "certs/server.crt",
"TLS_KEY": "certs/server.key",
```

and `docker compose restart`. `docker compose logs` now says `TLS on` and the
dashboard is `https://192.168.1.20:50001`. Phones install
`https://192.168.1.20:50001/ca.crt` as described in the README's
[HTTPS and phones](../README.md#https-and-phones); `server-data/certs/ca.key`
never leaves this computer.

## 5. Backups

In the console: `data backup` writes `pyhome-backup-<date>-<time>.db` into
`server-data/`, safe while the server runs. For everything (config,
certificates, database):

```
docker compose stop
```

copy the whole `server-data` folder somewhere safe, then
`docker compose start`.

## 6. Updating

```
git pull
docker compose up -d --build
```

The image is built anew; `server-data/` and `.env` stay as they are.

## 7. Moving an existing server into the container

The clients and their history come along:

1. Stop the old server: **Zastaviť** in the launcher, or `shutdown` and `y`
   in its console. A clean stop leaves no `pyhome.db-wal`.
2. Copy `config.json`, the `certs` folder and `pyhome.db` from `server/data/`
   into `server-data/` (make the folder if `docker compose up` has not yet).
3. Check that `HOST` and `WEB_HOST` in the copied `config.json` are `0.0.0.0`.
4. `docker compose up -d --build`. The logs say
   `Database /data/pyhome.db, N clients known`.
5. In the launcher, untick the server: the old one must not start again on
   the same ports.

Keep the old files until the clients have reconnected.

## 8. Hľadať servery, other computers and the firewall

On the computer that runs Docker, **Hľadať servery** in the launcher finds
the server. From other computers it depends on Docker's network:

- **Linux (a Pi, a NAS):** start it on the host's network, and every computer
  in the house finds it:

  ```
  docker compose -f docker-compose.yml -f docker-compose.host.yml up -d --build
  ```

  The printed address is then right without `PYHOME_ADDRESS`. Use the same
  two files for every later `docker compose` command.
- **Windows:** Docker Desktop forwards ports but not broadcasts, so other
  computers type the server's address into the client form.

Windows may ask once whether Docker may receive on the network; allow it for
private networks.

A port changed in `config.json` must be changed in `docker-compose.yml`'s
`ports` too (the host override needs nothing).

## 9. The launcher with the server in Docker

1. Untick the server in the launcher; Docker runs it now.
2. **+ Nový klient**, **Hľadať servery**. The server shows as `v sieti`, not
   `na tomto počítači`: its config is in `server-data/`, not in the checkout.
3. Compare the fingerprint in the list with the one in
   `docker compose logs` (`ca.crt at /ca.crt, SHA-256 ...`).
4. Type the token from `server-data/config.json`, keep TLS ticked: the
   launcher downloads the server's `ca.crt` and keeps it only when the
   fingerprint matches.
5. **Vytvoriť a spustiť**. The client's console says `Connected to ... (TLS)`.

## When something is wrong

| You see | Do |
| --- | --- |
| `docker ps` shows `unhealthy` or the container restarting | `docker compose logs` says why: a broken `config.json`, a missing certificate file |
| `Port 50000 ... is already in use` | the old server still runs, stop it (step 7) |
| `Permission denied` for `/data` on Linux | `sudo chown -R 1000 server-data` |
| A client cannot connect from another computer | the address and port in the client, `TOKEN` the same on both, the firewall |
| **Hľadať servery** finds nothing from another computer | expected on Windows; on Linux use the host override (step 8) |
