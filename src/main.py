"""
Author: Benjamin Noirat 
Date: 2026-04-02
"""

import asyncio
from feeds.binance import BinanceFeed
from feeds.coinbase import CoinbaseFeed
from strategy.strat_ben import StratBen

async def main():
    # Create feeds
    binance_feed = BinanceFeed("BTCUSDT")
    coinbase_feed = CoinbaseFeed("BTC-USD")
    feeds = [binance_feed, coinbase_feed]

    # Instantiate strategy and subscribe to feeds
    strat_1 = StratBen(feeds)

    # Run all feeds concurrently
    await asyncio.gather(*(feed.connect() for feed in feeds))

if __name__ == "__main__":
    asyncio.run(main())
