"""
Author: Benjamin Noirat 
Date: 2026-04-02
"""

from collections import defaultdict
from bisect import bisect_left, bisect_right
from core.constants import EPSILON
from core.types import BookLevel

class FeedOrderBook:
    def __init__(self, feed_name: str):
        self.feed_name = feed_name
        self.bids = defaultdict(dict)
        self.asks = defaultdict(dict)
        self.bid_prices = []  # descending
        self.ask_prices = []  # ascending

    def _update_prices_list(self, side: str, price: float):
        prices = self.bid_prices if side == 'bid' else self.ask_prices
        ascending = False if side == 'bid' else True
        if price not in prices:
            if ascending:
                i = bisect_right(prices, price)
            else:
                i = bisect_left([-p for p in prices], -price)
            prices.insert(i, price)

    def _remove_price_if_empty(self, side: str, price: float):
        book = self.bids if side == 'bid' else self.asks
        prices = self.bid_prices if side == 'bid' else self.ask_prices
        if price in book and not book[price]:
            del book[price]
            prices.remove(price)

    def update_level(self, side: str, price: float, size: float, exchange: str):
        book = self.bids if side == 'bid' else self.asks

        if size > EPSILON:
            book[price][exchange] = BookLevel(price=price, size=size, exchange=exchange)
            self._update_prices_list(side, price)
        else:
            if price in book and exchange in book[price]:
                del book[price][exchange]
                self._remove_price_if_empty(side, price)

    def get_best_bid(self):
        if not self.bid_prices:
            return None
        best_price = self.bid_prices[0]
        total_size = sum(lvl.size for lvl in self.bids[best_price].values())
        return best_price, total_size

    def get_best_ask(self):
        if not self.ask_prices:
            return None
        best_price = self.ask_prices[0]
        total_size = sum(lvl.size for lvl in self.asks[best_price].values())
        return best_price, total_size

    def get_mid(self):
        bid = self.get_best_bid()
        ask = self.get_best_ask()
        if bid and ask:
            return (bid[0] + ask[0]) / 2
        return None

    def get_book(self):
        """
        Return all BookLevels in sorted order (descending bids, ascending asks)
        """
        bids_list = []
        for price in self.bid_prices:
            bids_list.extend(self.bids[price].values())
        asks_list = []
        for price in self.ask_prices:
            asks_list.extend(self.asks[price].values())
        return {
            'bids': bids_list,
            'asks': asks_list
        }
