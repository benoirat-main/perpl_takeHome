"""
Author: Benjamin Noirat
Date: 2026-04-02
Updated: 2026-04-02
Binance feed with top-N fast-path, async full-book, and trade notifications
"""

import asyncio
import json
import websockets

from core.constants import EPSILON
from core.types import BookLevel
from core.order_book import FeedOrderBook, TOP_N


class BinanceFeed:
    def __init__(self, symbol: str):
        self.symbol = symbol.lower()
        self.book_name = "binance"
        self.book = FeedOrderBook(self.book_name)

        # Listeners
        self._book_listeners = []
        self._trade_listeners = []

        # Async queue for full book updates
        self._full_book_queue = asyncio.Queue()
        asyncio.create_task(self._process_full_book_queue())

        # Reconnect params
        self._reconnect_delay_seconds = 1
        self._max_reconnect_delay = 60

        # Stream URLs
        self._depth_url = f"wss://stream.binance.com:9443/ws/{self.symbol}@depth@100ms"
        self._trade_url = f"wss://stream.binance.com:9443/ws/{self.symbol}@trade"

    # ----------------- Subscription API -----------------
    def subscribe_book(self, callback):
        self._book_listeners.append(callback)

    def subscribe_trade(self, callback):
        self._trade_listeners.append(callback)

    # ----------------- Internal Notifiers -----------------
    async def _notify_book(self):
        for cb in self._book_listeners:
            await cb(self.book_name, self.book)

    async def _notify_trade(self, trade: BookLevel):
        for cb in self._trade_listeners:
            await cb(self.book_name, trade)

    # ----------------- WebSocket Connection -----------------
    async def connect(self):
        await asyncio.gather(
            self._connect_depth(),
            self._connect_trade()
        )

    async def _connect_depth(self):
        while True:
            try:
                async with websockets.connect(self._depth_url, max_size=None) as ws:
                    await self._listen_depth(ws)
            except Exception as e:
                print(f"[BinanceFeed] Depth connection error: {e}. Reconnecting in {self._reconnect_delay_seconds}s...")
                await asyncio.sleep(self._reconnect_delay_seconds)
                self._reconnect_delay_seconds = min(self._reconnect_delay_seconds * 2, self._max_reconnect_delay)

    async def _connect_trade(self):
        while True:
            try:
                async with websockets.connect(self._trade_url) as ws:
                    async for msg in ws:
                        data = json.loads(msg)
                        price = float(data['p'])
                        size = float(data['q'])
                        side = 'bid' if data['m'] is False else 'ask'  # 'm' = maker side (True if sell)
                        if size > EPSILON:
                            trade = BookLevel(price=price, size=size, exchange=self.book_name)
                            await self._notify_trade(trade)
            except Exception as e:
                print(f"[BinanceFeed] Trade connection error: {e}. Reconnecting in {self._reconnect_delay_seconds}s...")
                await asyncio.sleep(self._reconnect_delay_seconds)
                self._reconnect_delay_seconds = min(self._reconnect_delay_seconds * 2, self._max_reconnect_delay)

    # ----------------- Depth Stream Handling -----------------
    async def _listen_depth(self, ws):
        async for msg in ws:
            data = json.loads(msg)
            # Binance depth updates: 'b' (bids), 'a' (asks)
            changes = []
            for price_str, qty_str in data.get('b', []):
                changes.append(('buy', price_str, qty_str))
            for price_str, qty_str in data.get('a', []):
                changes.append(('sell', price_str, qty_str))

            await self._process_l2update_fast(changes)

    # ----------------- Fast-Path Top-N -----------------
    async def _process_l2update_fast(self, changes):
        top_updated = False

        # Phase 1: update top-N first
        for side_str, price_str, size_str in changes:
            price = float(price_str)
            size = float(size_str)
            side = 'bid' if side_str == 'buy' else 'ask'

            top_prices = self.book.bids_top_prices if side == 'bid' else self.book.asks_top_prices
            if price in top_prices or len(top_prices) < TOP_N or \
               (side == 'bid' and price > min(top_prices)) or \
               (side == 'ask' and price < max(top_prices)):
                old_top = self.book.get_top(side).copy()
                self.book.update_level(side, price, size, self.book_name)
                if self.book.get_top(side) != old_top:
                    top_updated = True

        if top_updated:
            await self._notify_book()

        # Phase 2: full book async
        for side_str, price_str, size_str in changes:
            price = float(price_str)
            size = float(size_str)
            side = 'bid' if side_str == 'buy' else 'ask'
            self._full_book_queue.put_nowait((side, price, size))

    # ----------------- Async Full Book Maintenance -----------------
    async def _process_full_book_queue(self):
        while True:
            side, price, size = await self._full_book_queue.get()
            self.book.update_level(side, price, size, self.book_name)
            self._full_book_queue.task_done()