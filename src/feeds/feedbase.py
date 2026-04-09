"""
Author: Benjamin Noirat 
Date: 2026-04-02
"""

import asyncio

from core.order_book import FeedOrderBook
import time

class FeedBase:
    def __init__(self, params):
        self.params = params
        self.book: FeedOrderBook = FeedOrderBook(self.params)

        self._book_listeners = []
        self._trade_listeners = []

        self._reconnect_delay_seconds = 1
        self._max_reconnect_delay = 60
        self.connected = False

        self.last_update_time = 0
        self.last_trade_time = 0

        self._full_book_queue = asyncio.Queue()
        asyncio.create_task(self._process_full_book_queue())

    def subscribe_book(self, callback):
        self._book_listeners.append(callback)

    def subscribe_trade(self, callback):
        self._trade_listeners.append(callback)

    def get_last_update_time(self):
        return self.last_update_time
    
    def get_last_trade_time(self):
        return self.last_trade_time

    async def _notify_book(self):
        for cb in self._book_listeners:
            await cb(self.feed_name, self.book)

    async def _notify_trade(self, trade):
        for cb in self._trade_listeners:
            await cb(self.feed_name, trade)

    async def _process_full_book_queue(self):
        while True:
            side, price, size, dt = await self._full_book_queue.get()
            self.book.update_level(side, price, size, self.feed_name, dt)
            self._full_book_queue.task_done()

    def get_status(self):
        now = time.time()
        last_message_ts = max(self.last_update_time, self.last_trade_time)
        stale = (now - last_message_ts) > 5 * 1000  # 5 seconds in milliseconds

        return {
            "connected": self.connected,
            "last_message_age": None if not last_message_ts else now - (last_message_ts / 1000),
            "last_message_ts":  None if not last_message_ts else last_message_ts,
            "stale": stale
        }