import asyncio
import ssl

from shared.colors import GREEN, RED, RESET
from shared.config import get_config, get_config_file, get_config_path
from shared.console import print_message
from shared.protocol import DENIED, HELLO, STATE, WELCOME, ProtocolError, read_message, send_message
from client_handlers.device_handler import GET_STATE, get_capabilities, get_device, run_action

RETRY_SECONDS = 15
HANDSHAKE_TIMEOUT = 10


class AccessDenied(Exception):
    """The server refused our hello. Retrying with the same token cannot help."""


class TLSRefused(Exception):
    """TLS cannot work as configured. Retrying with the same TLS_CA cannot help."""


def tls_context():
    """The SSLContext trusting TLS_CA, or None when the client has none. TLSRefused when it cannot be built."""
    ca = get_config_file("TLS_CA")
    if ca is None:
        return None
    try:
        context = ssl.create_default_context(cafile=ca)
    except FileNotFoundError as e:
        raise TLSRefused(f"TLS_CA file not found: {ca}") from e
    except ssl.SSLError as e:
        raise TLSRefused(f"TLS_CA is not a certificate: {ca}") from e
    # the chain is still checked against this house's authority, which signs
    # only this server; checking the host name as well would only break every
    # client the day the server's address changes
    context.check_hostname = False
    return context


def tls_warning():
    """The startup warning for a client that talks in plain text, or None."""
    if get_config("TLS_CA"):
        return None
    return "No TLS_CA set, the token and every message cross the network in plain text"


class Connection:
    """The link to the server, and everything that describes it.

    This used to be a handful of module globals with getters and setters.
    Keeping it in one object means the state cannot drift apart: a socket is
    never left behind on a connection that is marked as closed.
    """

    def __init__(self):
        self.connected = False
        self.reader = None
        self.writer = None
        self.server_info = {}
        self.auto_reconnect = False
        self.tls = False
        self.lock = asyncio.Lock()

    def attach(self, reader, writer, server_info, tls=False):
        self.reader = reader
        self.writer = writer
        self.server_info = server_info
        self.tls = tls
        self.connected = True
        self.auto_reconnect = False

    def detach(self):
        """Forget the socket and hand the writer back so the caller can close it."""
        writer = self.writer
        self.connected = False
        self.reader = None
        self.writer = None
        return writer

    @property
    def label(self):
        """host:port@name#id of the server, for printing."""
        info = self.server_info
        return (f"{info.get('host')}:{info.get('port')}"
                f"@{info.get('name')}#{info.get('id')}")


connection = Connection()


async def connect_to_server_async():
    tried_first = False

    while True:
        try:
            if not tried_first:
                print("Attempting first connection...")
                tried_first = True
            elif connection.connected or not connection.auto_reconnect:
                # nothing to do while connected or while auto reconnect is off
                await asyncio.sleep(1)
                continue

            async with connection.lock:
                if not connection.connected:
                    await handshake()

        except AccessDenied as e:
            connection.connected = False
            # the same token would be refused again, wait for the user instead
            connection.auto_reconnect = False
            print_message(f"{RED}Refused by the server{RESET}: {e}. "
                          f"Fix TOKEN in {get_config_path()}, then type 'reconnect'.")

        except TLSRefused as e:
            connection.connected = False
            # the same TLS_CA would fail again, the same as a refused token
            connection.auto_reconnect = False
            print_message(f"{RED}TLS refused{RESET}: {e}. "
                          f"Fix TLS_CA in {get_config_path()}, then type 'reconnect'.")

        except (OSError, ProtocolError, asyncio.TimeoutError) as e:
            connection.connected = False
            # keep trying, the server may simply not be up yet
            connection.auto_reconnect = True
            print_message(f"{RED}Server unavailable{RESET}: {e}")
            await asyncio.sleep(RETRY_SECONDS)

        except Exception as e:
            connection.connected = False
            # an unexpected error is no reason to stop trying for good
            connection.auto_reconnect = True
            print_message(f"{RED}Fatal connection error{RESET}: {e}")
            await asyncio.sleep(RETRY_SECONDS)


async def handshake():
    """Open a connection, say hello, and wait for the server to answer."""
    context = tls_context()
    reader, writer = await open_connection(context)

    # a numeric TOKEN in config.json is still a token, the server compares strings
    token = get_config("TOKEN")

    try:
        await send_message(
            writer, HELLO,
            id=get_config("ID"),
            name=get_config("NAME"),
            # the config's TYPE, client or server, "type" itself is the envelope field
            role=get_config("TYPE"),
            device=get_config("DEVICE") or None,
            capabilities=get_capabilities(),
            version=get_config("VERSION"),
            token=str(token) if token else None,
        )

        welcome = await asyncio.wait_for(read_message(reader), timeout=HANDSHAKE_TIMEOUT)

        if welcome is None:
            # a TLS server hangs up on a plain hello without a word
            hint = "" if context else f". If it uses TLS, set TLS_CA in {get_config_path()}"
            raise ConnectionError(f"server closed the connection during the handshake{hint}")
        if welcome["type"] == DENIED:
            raise AccessDenied(str(welcome.get("reason") or "no reason given"))
        if welcome["type"] != WELCOME:
            raise ProtocolError(f"expected '{WELCOME}', got '{welcome['type']}'")
    except BaseException:
        # nothing is attached yet, so nobody else would ever close this socket
        writer.close()
        raise

    connection.attach(reader, writer, welcome, tls=context is not None)
    print_message(f"Connected to {GREEN}{connection.label}{RESET}" + (" (TLS)" if connection.tls else ""))

    # the server keeps the last known state, give it one to start from
    if get_device() is not None:
        try:
            # optional: a failure here must not drop the connection we just attached
            await send_message(writer, STATE, state=await run_action(GET_STATE, {}))
        except Exception as e:
            print_message(f"{RED}Could not send the device state{RESET}: {e}")


async def open_connection(context):
    """(reader, writer) to HOST:PORT, through TLS when context is given.

    A certificate the authority did not sign raises TLSRefused. Any other TLS
    failure becomes a ConnectionError that says what to check, and is retried:
    the server may be restarting with its new config.
    """
    host, port = get_config("HOST"), get_config("PORT")
    if context is None:
        return await asyncio.open_connection(host, port)

    try:
        return await asyncio.open_connection(host, port, ssl=context, ssl_handshake_timeout=HANDSHAKE_TIMEOUT)
    except ssl.SSLCertVerificationError as e:
        # before OSError below: a rejected certificate is an OSError too
        raise TLSRefused(f"server certificate not trusted by TLS_CA: {e.verify_message}") from e
    except (ssl.SSLError, ConnectionResetError, ConnectionAbortedError, asyncio.TimeoutError) as e:
        # a refused connection is not caught here, the server is simply not up
        reason = str(e) or type(e).__name__
        raise ConnectionError(f"TLS handshake failed: {reason}. "
                              f"If the server does not use TLS, empty TLS_CA in {get_config_path()}") from e


async def send_to_server(message_type, /, **payload):
    """Send one message while holding the connection lock. False when not connected.

    Command results are sent from their own tasks, the lock keeps two of them
    from writing to the socket at the same time.
    """
    async with connection.lock:
        if not connection.connected or connection.writer is None:
            return False
        await send_message(connection.writer, message_type, **payload)
        return True
