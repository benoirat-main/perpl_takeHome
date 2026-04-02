import asyncio
import json
import websockets
from core.constants import EPSILON
from core.types import BookLevel
from core.order_book import FeedOrderBook

class CoinbaseFeed:
    def __init__(self, symbol: str):
        """
        symbol: e.g., "BTC-USD"
        """
        self.symbol = symbol.upper()
        self.book_name = "coinbase"
        self.book = FeedOrderBook(self.book_name)
        self.ws_url = "wss://ws-feed.exchange.coinbase.com"

        # Listeners
        self._book_listeners = []
        self._trade_listeners = []

        # Reconnect/backoff params
        self._reconnect_delay = 1  # initial delay in seconds
        self._max_reconnect_delay = 60

    # --- Subscription methods ---
    def subscribe_book(self, callback):
        """
        callback signature: async def callback(feed_name: str, book: FeedOrderBook)
        """
        self._book_listeners.append(callback)

    def subscribe_trade(self, callback):
        """
        callback signature: async def callback(feed_name: str, trade: BookLevel)
        """
        self._trade_listeners.append(callback)

    async def _notify_book(self):
        for cb in self._book_listeners:
            await cb(self.book_name, self.book)

    async def _notify_trade(self, trade: BookLevel):
        for cb in self._trade_listeners:
            await cb(self.book_name, trade)

    # --- Websocket connection ---
    async def connect(self):
        while True:
            try:
                async with websockets.connect(self.ws_url, max_size=None) as ws:
                    await self._subscribe(ws)
                    self._reconnect_delay = 1  # reset delay after successful connect
                    await self._listen(ws)
            except Exception as e:
                print(f"[CoinbaseFeed] Connection error: {e}. Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)

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

            if msg_type == "l2update":
                # Order book updates
                for change in data.get("changes", []):
                    side_str, price_str, size_str = change
                    price = float(price_str)
                    size = float(size_str)
                    self.book.update_level(side_str, price, size, self.book_name)
                await self._notify_book()

            elif msg_type == "match":
                # Trade updates
                price = float(data['price'])
                size = float(data['size'])
                if size > EPSILON:
                    trade = BookLevel(price=price, size=size, exchange=self.book_name)
                    await self._notify_trade(trade)