import asyncio
from rich.live import Live
from rich.table import Table
from rich.console import Console
from rich.columns import Columns
from datetime import datetime


async def display_book(feed_name, book, timestamp=None):
    """Return a rich Table of top-N bids/asks with optional timestamp"""
    ts_str = ""
    if timestamp:
        ts_str = datetime.fromtimestamp(timestamp / 1000).strftime("%Y%m%d %H:%M:%S.%f")[:-3]

    title = f"{feed_name}"
    if ts_str:
        title += f" (Last: {ts_str})"

    table = Table(title=title)

    table.add_column("Bid Size", justify="left")
    table.add_column("Bid Price", justify="right")
    table.add_column("Ask Price", justify="right")
    table.add_column("Ask Size", justify="left")

    top_bids = book.get_top('bid')
    top_asks = book.get_top('ask')
    keys_bid = list(top_bids.keys())
    keys_ask = list(top_asks.keys())
    max_depth = max(len(top_bids), len(top_asks))

    for i in range(max_depth):
        bid = top_bids[keys_bid[i]] if i < len(keys_bid) else None
        ask = top_asks[keys_ask[i]] if i < len(keys_ask) else None

        # formatting: price 2 decimals, size 5 decimals
        bid_price, bid_size = (f"{bid.price:.2f}", f"{bid.size:.5f}") if bid else ("-", "-")
        ask_price, ask_size = (f"{ask.price:.2f}", f"{ask.size:.5f}") if ask else ("-", "-")

        table.add_row(bid_size, bid_price, ask_price, ask_size)

    return table


async def run_cli(feeds):
    """Continuously render all feeds side by side in terminal"""
    console = Console()
    with Live(refresh_per_second=10, console=console) as live:
        while True:
            tables = []
            for feed in feeds:
                # if your feed object has a timestamp property, pass it here
                ts = feed.get_last_update_time()
                table = await display_book(feed.book_name, feed.book, timestamp=ts)
                tables.append(table)

            # Display all tables horizontally
            live.update(Columns(tables))
            await asyncio.sleep(0.05)  # 50ms refresh