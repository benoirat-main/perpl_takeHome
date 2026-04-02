"""
Author: Benjamin Noirat
Date: 2026-04-02
Updated: 2026-04-02
Fast-path top-N O(1) updates with full book in dicts
"""

from collections import defaultdict
from core.constants import EPSILON
from core.types import BookLevel

TOP_N = 10  # Number of top levels for fast-path

class FeedOrderBook:
    def __init__(self, feed_name: str):
        self.feed_name = feed_name

        # Full book (dict of dicts: price -> exchange -> BookLevel)
        self.bids = defaultdict(dict)
        self.asks = defaultdict(dict)

        # Top-N prices for fast access
        self.bids_top_prices = []
        self.asks_top_prices = []

        self.bids_top = {}  # price -> exchange -> BookLevel
        self.asks_top = {}  # price -> exchange -> BookLevel

    # ----------------- Update a single level -----------------
    def update_level(self, side: str, price: float, size: float, exchange: str):
        book = self.bids if side == 'bid' else self.asks
        top_dict = self.bids_top if side == 'bid' else self.asks_top
        top_prices = self.bids_top_prices if side == 'bid' else self.asks_top_prices
        ascending = side == 'ask'

        # --- Update full book dict ---
        if size > EPSILON:
            book.setdefault(price, {})[exchange] = BookLevel(price, size, exchange)
        else:
            if price in book and exchange in book[price]:
                del book[price][exchange]
                if not book[price]:
                    del book[price]

        # --- Update top-N if necessary ---
        if price in top_dict:
            # Already in top-N
            if size > EPSILON:
                top_dict[price][exchange] = BookLevel(price, size, exchange)
            else:
                del top_dict[price][exchange]
                if not top_dict[price]:
                    del top_dict[price]
                    top_prices.remove(price)
        else:
            # Not in top-N → check if it qualifies
            if len(top_prices) < TOP_N:
                # Add directly
                top_dict[price] = {exchange: BookLevel(price, size, exchange)}
                top_prices.append(price)
                self._sort_top_prices(side)
            else:
                # Compare with worst top level
                worst_price = top_prices[-1] if not ascending else top_prices[-1]
                if (not ascending and price > worst_price) or (ascending and price < worst_price):
                    # Replace worst
                    removed_price = top_prices.pop(-1)
                    del top_dict[removed_price]
                    # Insert new
                    top_dict[price] = {exchange: BookLevel(price, size, exchange)}
                    top_prices.append(price)
                    self._sort_top_prices(side)

    # ----------------- Sort top-N prices -----------------
    def _sort_top_prices(self, side: str):
        # sorting time negligeable for top 10 prices
        top_prices = self.bids_top_prices if side == 'bid' else self.asks_top_prices
        top_prices.sort(reverse=(side == 'bid'))  # bids descending, asks ascending

    # ----------------- Top-N retrieval -----------------
    def get_top(self, side: str):
        return self.bids_top if side == 'bid' else self.asks_top

    # ----------------- Best bid/ask -----------------
    def get_best_bid(self):
        if not self.bids_top_prices:
            return None
        price = self.bids_top_prices[0]
        total_size = sum(lvl.size for lvl in self.bids_top[price].values())
        return price, total_size

    def get_best_ask(self):
        if not self.asks_top_prices:
            return None
        price = self.asks_top_prices[0]
        total_size = sum(lvl.size for lvl in self.asks_top[price].values())
        return price, total_size

    def get_mid(self):
        bid = self.get_best_bid()
        ask = self.get_best_ask()
        if bid and ask:
            return (bid[0] + ask[0]) / 2
        return None

    # ----------------- Full book retrieval (for logging / async) -----------------
    def get_full_book(self):
        return {
            'bids': {price: lvl.copy() for price, lvl in self.bids.items()},
            'asks': {price: lvl.copy() for price, lvl in self.asks.items()}
        }