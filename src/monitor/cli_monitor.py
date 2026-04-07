import asyncio
from rich.live import Live
from rich.table import Table
from rich.console import Console
from rich.columns import Columns
from datetime import datetime
from core.constants import EPSILON


async def display_book(feed_name, book, active_orders, timestamp=None):
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

    # Get top book prices and map price -> entry
    top_bids = book.get_top('bid').copy()
    top_asks = book.get_top('ask').copy()
    bid_prices = book.bids_top_prices.copy()
    ask_prices = book.asks_top_prices.copy()

    # Merge active orders into the book prices
    for order in active_orders:
        if order['side'] == 'bid':
            bid_prices.append(order['price'] - EPSILON)
            top_bids[order['price'] - EPSILON] = order  # Add a small espilon to simulate we enter at back of queue
        elif order['side'] == 'ask':
            ask_prices.append(order['price'] + EPSILON)
            top_asks[order['price'] + EPSILON] = order

    # Sort bids descending, asks ascending
    bid_prices.sort(reverse=True)
    ask_prices.sort()

    # Compute max depth
    max_depth = max(len(bid_prices), len(ask_prices))

    for i in range(max_depth):
        # Bid
        if i < len(bid_prices):
            price = bid_prices[i]
            bid = top_bids.get(price)
            bid_price_str = f"{bid['price']:.2f}" if isinstance(bid, dict) else f"{bid.price:.2f}"
            bid_size_str = f"{bid['size']:.6f}" if isinstance(bid, dict) else f"{bid.size:.6f}"
            # Color active order red
            if isinstance(bid, dict) and bid.get('side') == 'bid':
                bid_price_str = f"[red]{bid_price_str}[/red]"
                bid_size_str = f"[red]{bid_size_str}[/red]"
        else:
            bid_price_str, bid_size_str = "-", "-"

        # Ask
        if i < len(ask_prices):
            price = ask_prices[i]
            ask = top_asks.get(price)
            ask_price_str = f"{ask['price']:.2f}" if isinstance(ask, dict) else f"{ask.price:.2f}"
            ask_size_str = f"{ask['size']:.6f}" if isinstance(ask, dict) else f"{ask.size:.6f}"
            if isinstance(ask, dict) and ask.get('side') == 'ask':
                ask_price_str = f"[red]{ask_price_str}[/red]"
                ask_size_str = f"[red]{ask_size_str}[/red]"
        else:
            ask_price_str, ask_size_str = "-", "-"

        table.add_row(bid_size_str, bid_price_str, ask_price_str, ask_size_str)

    return table


async def run_cli(feeds, strategy):
    """Continuously render all feeds side by side in terminal"""
    console = Console()
    with Live(refresh_per_second=10, console=console) as live:
        while True:
            tables = []
            for feed in feeds:
                # if your feed object has a timestamp property, pass it here
                ts = feed.get_last_update_time()
                orders = strategy.active_orders[feed.feed_name] if len(strategy.active_orders) > 0 else []
                table = await display_book(feed.feed_name, feed.book, orders, timestamp=ts)
                tables.append(table)

            # Display all tables horizontally
            live.update(Columns(tables))
            await asyncio.sleep(0.05)  # 50ms refresh