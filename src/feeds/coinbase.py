"""
Author: Benjamin Noirat
Date: 2026-04-02
Updated: 2026-04-02
Top-N fast-path updates first, full book async after
"""

import asyncio
import json
import websockets

from core.constants import EPSILON
from core.types import BookLevel
from core.order_book import FeedOrderBook, TOP_N


class CoinbaseFeed:
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self.book_name = "coinbase"
        self.book = FeedOrderBook(self.book_name)
        self.ws_url = "wss://ws-feed.exchange.coinbase.com"

        # Listeners
        self._book_listeners = []
        self._trade_listeners = []

        # Async queue for full book updates
        self._full_book_queue = asyncio.Queue()

        # Background task to process full book asynchronously
        asyncio.create_task(self._process_full_book_queue())

        # Reconnect params
        self._reconnect_delay_seconds = 1
        self._max_reconnect_delay = 60

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
        while True:
            try:
                async with websockets.connect(self.ws_url, max_size=None) as ws:
                    await self._subscribe(ws)
                    self._reconnect_delay_seconds = 1
                    await self._listen(ws)
            except Exception as e:
                print(f"[CoinbaseFeed] Connection error: {e}. Reconnecting in {self._reconnect_delay_seconds}s...")
                await asyncio.sleep(self._reconnect_delay_seconds)
                self._reconnect_delay_seconds = min(self._reconnect_delay_seconds * 2, self._max_reconnect_delay)

    async def _subscribe(self, ws):
        msg = {
            "type": "subscribe",
            "product_ids": [self.symbol],
            "channels": ["level2_batch", "matches"]
        }
        await ws.send(json.dumps(msg))
        print(f"[CoinbaseFeed] Subscribed to {self.symbol} channels.")

    async def _listen(self, ws):
        async for msg in ws:
            data = json.loads(msg)
            msg_type = data.get("type")

            if msg_type == "snapshot":
                # Initialize full book
                for side in ['bids', 'asks']:
                    for price_str, size_str in data[side]:
                        price = float(price_str)
                        size = float(size_str)
                        self.book.update_level(side[:-1], price, size, self.book_name)
                # Notify top-N fast path
                await self._notify_book()

            elif msg_type == "l2update":
                changes = data.get("changes", [])
                await self._process_l2update_fast(changes)

            elif msg_type == "match":
                price = float(data['price'])
                size = float(data['size'])
                if size > EPSILON:
                    trade = BookLevel(price=price, size=size, exchange=self.book_name)
                    await self._notify_trade(trade)

    # ----------------- Fast-Path Top-N -----------------
    async def _process_l2update_fast(self, changes):
        """Process level2_batch changes in two phases: top-N first, full book async later"""
        top_updated = False

        # --- Phase 1: update only top-N ---
        for side_str, price_str, size_str in changes:
            price = float(price_str)
            size = float(size_str)
            side = 'bid' if side_str == 'buy' else 'ask'

            # Check if the level is in top-N or qualifies for top-N
            top_prices = self.book.bids_top_prices if side == 'bid' else self.book.asks_top_prices
            if price in top_prices or len(top_prices) < TOP_N or \
               (side == 'bid' and price > min(top_prices)) or \
               (side == 'ask' and price < max(top_prices)):
                self.book.update_level(side, price, size, self.book_name)

        # Notify strategy immediately after top-N update
        if top_updated:
            await self._notify_book()

        # --- Phase 2: update full book asynchronously ---
        for side_str, price_str, size_str in changes:
            price = float(price_str)
            size = float(size_str)
            side = 'bid' if side_str == 'buy' else 'ask'
            # Push all changes to the queue for background processing
            self._full_book_queue.put_nowait((side, price, size))

    # ----------------- Async Full Book Maintenance -----------------
    async def _process_full_book_queue(self):
        """Background task to maintain full book (already updated in top-N)"""
        while True:
            side, price, size = await self._full_book_queue.get()
            # Update the full book (skip top-N fast path if you want)
            self.book.update_level(side, price, size, self.book_name)
            self._full_book_queue.task_done()