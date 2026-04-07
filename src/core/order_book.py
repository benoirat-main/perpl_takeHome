"""
Author: Benjamin Noirat
Date: 2026-04-02
Updated: 2026-04-02
Fast-path top-N O(1) updates with full book in dicts
"""

from collections import defaultdict
from core.constants import EPSILON
from core.types import BookLevel

TOP_N = 20  # Number of top levels for fast-path

class FeedOrderBook:
    def __init__(self, params):
        self.params = params

        # Full book (dict of dicts: price  -> BookLevel)
        self.bids = defaultdict(dict)
        self.asks = defaultdict(dict)

        # Top-N prices for fast access
        self.bids_top_prices = []
        self.asks_top_prices = []

        self.bids_top = {}  # price -> BookLevel
        self.asks_top = {}  # price -> BookLevel

    # ----------------- Update a single level -----------------
    def update_level(self, side: str, price: float, size: float, exchange: str):
        book = self.bids if side == 'bid' else self.asks
        top_dict = self.bids_top if side == 'bid' else self.asks_top
        top_prices = self.bids_top_prices if side == 'bid' else self.asks_top_prices
        ascending = side == 'ask'

        # --- Update full book dict ---
        if size > EPSILON:
            book['price'] = BookLevel(price, size, exchange)
        else:
            if price in book:
                del book[price]
                if not book[price]:
                    del book[price]

        # --- Update top-N if necessary ---
        if price in top_dict:
            # Already in top-N
            if size > EPSILON:
                top_dict[price] = BookLevel(price, size, exchange)
            else:
                del top_dict[price]
                top_prices.remove(price)
        else:
            # Not in top-N → check if it qualifies
            if size > EPSILON:
                if len(top_prices) < TOP_N:
                    # Add directly
                    top_dict[price] = BookLevel(price, size, exchange)
                    top_prices.append(price)
                    self._sort_top_prices(side)
                else:
                    # Compare with worst top level
                    worst_price = top_prices[-1] if not ascending else top_prices[-1]
                    if (not ascending and price > worst_price) or (ascending and price < worst_price):
                        # Reemove worst
                        top_prices.pop(-1)
                        del top_dict[worst_price]
                        # Insert new
                        top_dict[price] = BookLevel(price, size, exchange)
                        top_prices.append(price)
                        self._sort_top_prices(side)
        # Sanity check, could be removed from the fast path once we are happy with it
        if 'debug' in self.params and self.params['debug']:
            if len(top_prices) != len(top_dict):
                print(f"[{self.feed_name}] Warning: top_prices and top_dict length mismatch for {side}.")

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
        size = self.bids_top[price].size
        return price, size

    def get_best_ask(self):
        if not self.asks_top_prices:
            return None
        price = self.asks_top_prices[0]
        size = self.asks_top[price].size
        return price, size

    def get_mid(self):
        bid = self.get_best_bid()
        ask = self.get_best_ask()
        if bid and ask:
            return (bid[0] + ask[0]) / 2
        return None

    # ----------------- Book retrieval -----------------
    def get_full_book(self):
        # slower but I don't expect it to be called in the fast path
        return {
            'bids': {price: lvl.copy() for price, lvl in self.bids.items()},
            'asks': {price: lvl.copy() for price, lvl in self.asks.items()}
        }
    
    def get_top_book(self):

        return []
        # top_book = {'bids': {}, 'asks': {}}
        # for idx, price in enumerate(self.bids_top_prices):
        #     top_book['bids'][idx] = self.bids_top[price]

        # return {    
        #     'bids': {price: lvl.copy() for price, lvl in self.bids_top.items()},
        #     'asks': {price: lvl.copy() for price, lvl in self.asks_top.items()}
        # }