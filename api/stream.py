import asyncio

# Global queue for SSE
log_queue = asyncio.Queue()

def log(msg: str):
    """
    Called by synchronous or asynchronous scripts to push a log line to the browser.
    If called from a sync context, it safely pushes to the async event loop queue.
    """
    print(msg) # Still print to console
    try:
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(log_queue.put_nowait, msg)
    except RuntimeError:
        # If no running event loop (e.g. running scripts from CLI directly), just ignore
        pass

async def event_generator():
    """
    Yields log messages as Server-Sent Events.
    """
    while True:
        msg = await log_queue.get()
        yield f"data: {msg}\n\n"
