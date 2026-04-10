"""
Author: Benjamin Noirat 
Date: 2026-04-02
"""

import asyncio
from feeds.binance import BinanceFeed
from feeds.coinbase import CoinbaseFeed
from strategy.strat_ben import StratBen
from configs import config_strat_ben
from core import order_book
import monitor.cli_monitor

async def main():
    # Create feeds
    params = config_strat_ben.get_params()

    # Config Sanity checks
    if params['fair_value']['top_n'] > order_book.TOP_N:
        raise ValueError("top_n must be less than or equal to the order book TOP_N for the feeds")

    # For now we limit 1 instrument per feed, in live we would obviously want more.
    binance_feed = BinanceFeed({"symbol": params['symbol']})
    coinbase_feed = CoinbaseFeed({"symbol": params['symbol']})
    params['feeds'] = [binance_feed, coinbase_feed]

    # Instantiate strategy and subscribe to feeds
    strat = StratBen(params)
    # hack to feed position to strat via input file, as per assignment
    async def watch_position(strat, interval=1.0):
        while True:
            await strat.load_position()
            await asyncio.sleep(interval)

    if params['prints']['use_cli_monitor']:
        await asyncio.gather(
            monitor.cli_monitor.run_cli(params['feeds'], strat),
            *(feed.connect() for feed in params['feeds']),
            watch_position(strat)
        )
    else:
        await asyncio.gather(
            *(feed.connect() for feed in params['feeds']),
            watch_position(strat)
        )

if __name__ == "__main__":
    asyncio.run(main())
