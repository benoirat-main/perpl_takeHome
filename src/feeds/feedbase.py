"""
Author: Benjamin Noirat 
Date: 2026-04-02
"""

import asyncio

from core.order_book import FeedOrderBook


class FeedBase:
    def __init__(self, book_name: str):
        self.book_name = book_name
        self.book = FeedOrderBook(self.book_name)

        self._book_listeners = []
        self._trade_listeners = []

        self._reconnect_delay_seconds = 1
        self._max_reconnect_delay = 60

        self.last_update_time = 0
        self.last_trade_time = 0

        self._full_book_queue = asyncio.Queue()
        asyncio.create_task(self._process_full_book_queue())

    def subscribe_book(self, callback):
        # TODO: for now we build our book from cumulated changes. We can also subscribe to a snapshot channel and build the book from there, which would be more robust to connection issues.
        self._book_listeners.append(callback)

    def subscribe_trade(self, callback):
        self._trade_listeners.append(callback)

    def get_last_update_time(self):
        return self.last_update_time
    
    def get_last_trade_time(self):
        return self.last_trade_time

    async def _notify_book(self):
        for cb in self._book_listeners:
            await cb(self.book_name, self.book)

    async def _notify_trade(self, trade):
        for cb in self._trade_listeners:
            await cb(self.book_name, trade)

    async def _process_full_book_queue(self):
        while True:
            side, price, size = await self._full_book_queue.get()
            self.book.update_level(side, price, size, self.book_name)
            self._full_book_queue.task_done()