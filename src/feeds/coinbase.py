"""
Author: Benjamin Noirat 
Date: 2026-04-02
"""

import asyncio
import json
import websockets
from core.constants import EPSILON
from core.types import BookLevel
from core.order_book import FeedOrderBook

class CoinbaseFeed:
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self.book_name = "coinbase"
        self.book = FeedOrderBook(self.book_name)
        self.ws_url = "wss://ws-feed.exchange.coinbase.com"

        # Listeners
        self._book_listeners = []
        self._trade_listeners = []

        self._reconnect_delay_seconds = 1
        self._max_reconnect_delay = 60

    def subscribe_book(self, callback):
        self._book_listeners.append(callback)

    def subscribe_trade(self, callback):
        self._trade_listeners.append(callback)

    async def _notify_book(self):
        for cb in self._book_listeners:
            await cb(self.book_name, self.book)

    async def _notify_trade(self, trade: BookLevel):
        for cb in self._trade_listeners:
            await cb(self.book_name, trade)

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
                self._reconnect_delay_seconds = min(self._reconnect_delay_seconds * 2, self._reconnect_delay_seconds)

    async def _subscribe(self, ws):
        # here I have to subscribe to level2_batch which 50ms batchees, as the live tick by tick version requires authentication
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

            if msg_type == "l2update":
                for change in data.get("changes", []):
                    side_str, price_str, size_str = change
                    price = float(price_str)
                    size = float(size_str)
                    self.book.update_level(side_str, price, size, self.book_name)
                await self._notify_book()

            elif msg_type == "match":
                price = float(data['price'])
                size = float(data['size'])
                if size > EPSILON:
                    trade = BookLevel(price=price, size=size, exchange=self.book_name)
                    await self._notify_trade(trade)