import asyncio
import json
import websockets
from core.constants import EPSILON
from core.types import BookLevel
from core.order_book import FeedOrderBook

class BinanceFeed:
    def __init__(self, symbol: str):
        self.symbol = symbol.lower()
        self.book_name = "binance"
        self.book = FeedOrderBook(self.book_name)
        self.ws_depth_url = f"wss://stream.binance.com:9443/ws/{self.symbol}@depth@100ms"
        self.ws_trades_url = f"wss://stream.binance.com:9443/ws/{self.symbol}@trade"

        # Callbacks
        self._book_listeners = []
        self._trade_listeners = []

    # Subscription methods
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
        await asyncio.gather(
            self._listen_depth(),
            self._listen_trades()
        )

    async def _listen_depth(self):
        async with websockets.connect(self.ws_depth_url) as ws:
            async for msg in ws:
                data = json.loads(msg)

                for price_str, size_str in data.get("b", []):
                    price = float(price_str)
                    size = float(size_str)
                    self.book.update_level('bid', price, size, self.book_name)

                for price_str, size_str in data.get("a", []):
                    price = float(price_str)
                    size = float(size_str)
                    self.book.update_level('ask', price, size, self.book_name)

                await self._notify_book()

    async def _listen_trades(self):
        async with websockets.connect(self.ws_trades_url) as ws:
            async for msg in ws:
                data = json.loads(msg)
                price = float(data['p'])
                size = float(data['q'])
                if size > EPSILON:
                    trade = BookLevel(price=price, size=size, exchange=self.book_name)
                    await self._notify_trade(trade)