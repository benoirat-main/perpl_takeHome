"""
Author: Benjamin Noirat 
Date: 2026-04-02
"""

import asyncio
from feeds.binance import BinanceFeed
from feeds.coinbase import CoinbaseFeed
from strategy.strat_ben import StratBen
from collections import defaultdict
import monitor.cli_monitor

async def main():
    # Create feeds
    params = defaultdict(dict)

    params['prints'] = {
        'data_updates'    : False,
        'internal_book'   : False,
        'use_cli_monitor' : True
    }
    params['debug'] = True

    binance_feed = BinanceFeed({"symbol": "BTCUSDT"})
    coinbase_feed = CoinbaseFeed({"symbol": "BTC-USD"})
    params['feeds'] = [binance_feed, coinbase_feed]

    # Instantiate strategy and subscribe to feeds
    strat_1 = StratBen(params)

    if params['prints']['use_cli_monitor']:
        await asyncio.gather(
            monitor.cli_monitor.run_cli(params['feeds']),
            *(feed.connect() for feed in params['feeds'])
        )
    else:
        await asyncio.gather(
            *(feed.connect() for feed in params['feeds'])
        )

if __name__ == "__main__":
    asyncio.run(main())
