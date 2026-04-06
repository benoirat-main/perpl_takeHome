
"""
Author: Benjamin Noirat 
Date: 2026-04-02
"""

class StratBen:
    def __init__(self, params):
        # subscribe to all feeds
        self.params = params
        for feed in params['feeds']:
            feed.subscribe_book(self.on_book_update)
            feed.subscribe_trade(self.on_trade_update)

    async def on_book_update(self, feed_name: str, book):
        best_bid = book.get_best_bid()
        best_ask = book.get_best_ask()
        mid = book.get_mid()
        if self.params['prints']['data_updates']:
            print(f"{feed_name} book: bid {best_bid}, ask {best_ask}, mid {mid}")
        if self.params['prints']['internal_book']:
            print(f"TODO")

    async def on_trade_update(self, feed_name: str, trade):
        if self.params['prints']['data_updates']:
            print(f"{feed_name} trade: {trade.size}@{trade.price}")