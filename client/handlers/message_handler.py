import asyncio
from utils.colors import GREEN, RESET
from handlers.connection_handler import get_connection_state, get_connection_lock, set_connected

async def receive_messages_async():
    while True:
        try:
            CONNECTED, reader, writer, server_info = get_connection_state()
            connection_lock = get_connection_lock()
            
            async with connection_lock:
                if not CONNECTED or reader is None:
                    await asyncio.sleep(0.5)
                    continue
            
            try:
                # Read with timeout
                data = await asyncio.wait_for(reader.read(1024), timeout=0.5)
                
                if data:
                    message = data.decode('utf-8')
                    print(f"\nfrom {GREEN}{server_info['host']}:{server_info['port']}@{server_info['name']}{RESET} {message}")
                    print("> ", end="", flush=True)
            
            except asyncio.TimeoutError:
                pass
            
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                async with connection_lock:
                    set_connected(False)
                print(f"\n{RESET}Connection lost{RESET}")
                break
        
        except Exception as e:
            async with connection_lock:
                set_connected(False)
            print(f"\nError receiving: {e}")
            await asyncio.sleep(1)