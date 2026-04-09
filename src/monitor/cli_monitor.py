import asyncio
from rich.live import Live
from rich.table import Table
from rich.console import Console
from rich.columns import Columns
from datetime import datetime
import time
from core.constants import EPSILON
from core.order_book import FeedOrderBook
from core.types import BookLevel, Order
from feeds.feedbase import FeedBase
from strategy.strat_ben import StratBen as Strategy # Ideally we would create a stratgey interface to not make this code depend on specific strats


async def display_book(feed_name: str, book: FeedOrderBook, active_orders: list[Order], status=None):
    ts_str = ""
    ms_str = "-"
    st_str = "True"
    if status:
        ts_str = datetime.fromtimestamp(status['last_message_ts'] / 1000).strftime("%Y%m%d %H:%M:%S.%f")[:-3] if status['last_message_ts'] else "N/A"
        ms_str = f"{status['last_message_age']:.3f}" if status['last_message_age'] else "N/A"
        st_str = "True" if status['stale'] else "False"
    title = f"{feed_name}"
    title += f" (Last update: {ts_str} ({ms_str}s old)\nStale: {st_str})"

    active_buy_prices = []
    active_sell_prices = []
    now = time.time()

    table = Table(title=title)
    table.add_column("Age(s)", justify="left")
    table.add_column("Bid Size", justify="left")
    table.add_column("Bid Price", justify="right")
    table.add_column("Ask Price", justify="right")
    table.add_column("Ask Size", justify="left")
    table.add_column("Age(s)", justify="left")

    # Get top book prices and map price -> entry
    top_bids = book.get_top('bid').copy()
    top_asks = book.get_top('ask').copy()
    bid_prices = book.bids_top_prices.copy()
    ask_prices = book.asks_top_prices.copy()

    # Merge active orders into the book prices
    for order in active_orders:
        if order.side == 'bid':
            px           = order.price - EPSILON # Add a small espilon to simulate we enter at back of queue for this displaying
            top_bids[px] = BookLevel('buy', px, order.size, order.exchange, order.ts_sent)
            bid_prices.append(px)
            active_buy_prices.append(px)
        elif order.side == 'ask':
            px           = order.price + EPSILON
            top_asks[px] = BookLevel('sell', px, order.size, order.exchange, order.ts_sent)
            ask_prices.append(px)
            active_sell_prices.append(px)
    # Sort bids descending, asks ascending
    bid_prices.sort(reverse=True)
    ask_prices.sort()

    # Compute max depth
    max_depth = max(len(bid_prices), len(ask_prices))

    for i in range(max_depth):
        # Bid
        if i < len(bid_prices):
            price         = bid_prices[i]
            bid           = top_bids.get(price)
            bid_price_str = f"{bid.price:.2f}" if isinstance(bid, BookLevel) else f"-"
            bid_size_str  = f"{bid.size:.6f}" if isinstance(bid, BookLevel) else f"-"
            bid_age_str   = f"{(now - bid.last_update / 1000):.1f}" if isinstance(bid, BookLevel) else "-"
            # Color active order red
            if price in active_buy_prices and isinstance(bid, (BookLevel, Order)):
                bid_price_str = f"[red]{bid_price_str}[/red]"
                bid_size_str  = f"[red]{bid_size_str}[/red]"
                bid_age_str   = f"[red]{bid_age_str}[/red]"
        else:
            bid_price_str, bid_size_str, bid_age_str = "-", "-", "-"

        # Ask
        if i < len(ask_prices):
            price         = ask_prices[i]
            ask           = top_asks.get(price)
            ask_price_str = f"{ask.price:.2f}" if isinstance(ask, BookLevel) else f"-"
            ask_size_str  = f"{ask.size:.6f}" if isinstance(ask, BookLevel) else f"-"
            ask_age_str   = f"{(now - ask.last_update / 1000):.1f}" if isinstance(ask, BookLevel) else "-"
            if price in active_sell_prices and isinstance(ask, (BookLevel, Order)):
                ask_price_str = f"[red]{ask_price_str}[/red]"
                ask_size_str  = f"[red]{ask_size_str}[/red]"
                ask_age_str   = f"[red]{ask_age_str}[/red]"
        else:
            ask_price_str, ask_size_str, ask_age_str = "-", "-", "-"

        table.add_row(bid_age_str, bid_size_str, bid_price_str, ask_price_str, ask_size_str, ask_age_str)

    return table


async def run_cli(feeds: list[FeedBase], strategy: Strategy):
    """Continuously render all feeds side by side in terminal"""
    console = Console()
    with Live(refresh_per_second=10, console=console) as live:
        while True:
            tables = []
            for feed in feeds:
                orders = strategy.active_orders[feed.feed_name] if len(strategy.active_orders) > 0 else []
                table = await display_book(feed.feed_name, feed.book, orders, status=feed.get_status())
                tables.append(table)

            # Display all tables horizontally
            live.update(Columns(tables))
            await asyncio.sleep(0.05)  # 50ms refresh