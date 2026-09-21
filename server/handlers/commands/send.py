from shared.colors import GREEN, GRAY, RESET
from shared.symbols import SUCCESS, ERROR
from handlers.client_handler import get_connected_clients, send_to_clients

command = ["send", "msg"]
description = "Send a message to a client: send <id|all> <message>"


async def function(*params):
    if len(params) < 2:
        print(f"{ERROR} Usage: send <client id|all> <message>")

        online = get_connected_clients()
        if online:
            ids = ", ".join(sorted({info["id"] for info in online.values()}))
            print(f"{GRAY}      online: {ids}{RESET}")
        else:
            print(f"{GRAY}      no clients are connected{RESET}")
        return

    target = params[0]
    text = " ".join(params[1:])

    delivered, failed = await send_to_clients(target, text)

    if not delivered and not failed:
        print(f"{ERROR} No client matched '{target}'.")
        return

    for label in delivered:
        print(f"{SUCCESS} sent to {GREEN}{label}{RESET}: {text}")

    for label in failed:
        print(f"{ERROR} could not send to {label}")
