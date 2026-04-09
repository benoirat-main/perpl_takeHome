"""
Author: Benjamin Noirat 
Date: 2026-04-02
"""

import asyncio
import code
from feeds.binance import BinanceFeed
from feeds.coinbase import CoinbaseFeed
from strategy.strat_ben import StratBen
from collections import defaultdict
from core import order_book
import monitor.cli_monitor

async def main():
    # Create feeds
    params = defaultdict(dict)

    params['prints'] = {
        'data_updates'    : False,
        'internal_book'   : False,
        'use_cli_monitor' : True,
        'orders'          : False
    }
    params['debug'] = True
    params['symbol'] = 'BTCUSD'
    params['position_file'] = "src/position.json" # file to modify position, as per assignment
    # the following are given in price, it could also be in % of mid price etc
    params['fair_value'] = {
        'uncross_consolidated_book' : False, # whether to filter out crossed levels in the consolidated book before calculating fair value. This looses a lot if info when exchanges are far apart
        'top_n'                     : 20, # how many levels to consideer for the fair value calculation, limited by the size of fast path order_book
        'quote_half_life_seconds'   : 5.0 * 60.0 # decays thee wieght if unchanged quotes
    }
    params['quotes'] = {
        'spread_fixed'   : 0.02, # price offset to the fair value to produce our quotes
        'spread_vola'    : 0.0, # TODO: extra spread based on trailing volatility
        'spread_max_pos' : 10.0, # max extra spread based on position, in price
        'size'           : 0.15, # size of our quotes
        'max_share_mkt'  : 0.1 # max size compared to total volume on top_n levels
    }
    params['risk_limits'] = {
        'max_position'        : 1.0, # max position in the asset, in size
        'max_position_global' : 1000000 # TODO if we add more assets,max global position in USD across all assets
    }

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
