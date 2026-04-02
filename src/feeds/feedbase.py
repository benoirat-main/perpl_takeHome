"""
Author: Benjamin Noirat 
Date: 2026-04-02
"""

class FeedBase:
    def __init__(self):
        self._book_listeners = []
        self._trade_listeners = []

    def subscribe_book(self, callback):
        # TODO: for now we build our book from cumulated changes. We can also subscribe to a snapshot channel and build the book from there, which would be more robust to connection issues.
        self._book_listeners.append(callback)

    def subscribe_trade(self, callback):
        self._trade_listeners.append(callback)

    async def _notify_book(self):
        for cb in self._book_listeners:
            await cb(self.book_name, self.book)

    async def _notify_trade(self, trade):
        for cb in self._trade_listeners:
            await cb(self.book_name, trade)