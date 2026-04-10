"""
Author: Benjamin Noirat
Date: 2026-04-02
Updated: 2026-04-02
Binance feed with top-N fast-path, async full-book, and trade notifications
"""

import asyncio
import json
import sys
import websockets

from core.constants import EPSILON, CONTRACT_SPECS
from core.types import Trade
from core.order_book import TOP_N
from feeds.feedbase import FeedBase


class BinanceFeed(FeedBase):
    def __init__(self, params):
        super().__init__(params)
        self.feed_name = "binance"
        self.symbol = CONTRACT_SPECS[self.params['symbol']][self.feed_name]["symbol"].lower()

        # Stream URLs
        self._depth_url = f"wss://stream.binance.com:9443/ws/{self.symbol}@depth@100ms"
        self._trade_url = f"wss://stream.binance.com:9443/ws/{self.symbol}@trade"

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
                    self.connected = True
                    await self._listen_depth(ws)
            except Exception as e:
                print(f"[{self.feed_name} Depth connection error: {e}. Reconnecting in {self._reconnect_delay_seconds}s...")
                await asyncio.sleep(self._reconnect_delay_seconds)
                self._reconnect_delay_seconds = min(self._reconnect_delay_seconds * 2, self._max_reconnect_delay)

    async def _connect_trade(self):
        while True:
            try:
                async with websockets.connect(self._trade_url) as ws:
                    self.connected = True
                    self._reconnect_delay_seconds = 1  # reset on successful connect
                    async for msg in ws:
                        await self._listen_trade(msg)
            except Exception as e:
                self.connected = False
                print(f"[{self.feed_name}] Connection error: {e}. Reconnecting in {self._reconnect_delay_seconds}s...")
                await asyncio.sleep(self._reconnect_delay_seconds)
                self._reconnect_delay_seconds = min(
                    self._reconnect_delay_seconds * 2,
                    self._max_reconnect_delay
                )

    # ----------------- Trade Stream Handling -----------------
    async def _listen_trade(self, msg):
        try:
            data = json.loads(msg)
            timestamp = data['E']  # milliseconds since epoch
            if timestamp < self.last_trade_time:
                print(f"[{self.feed_name}] Out-of-order trade ignored (ts {timestamp} < last {self.last_trade_time})")
                return
            self.last_trade_time = timestamp
            price = float(data['p'])
            size = float(data['q'])
            if size <= EPSILON:
                return
            trade = Trade(
                exchange=self.feed_name,
                price=price,
                size=size,
                timestamp=timestamp
            )
            await self._notify_trade(trade)
        except Exception as e:
            print(f"[{self.feed_name}] Trade processing error: {e}")

    # ----------------- Depth Stream Handling -----------------
    async def _listen_depth(self, ws):
        try:
            async for msg in ws:
                data = json.loads(msg)
                if self.last_update_time <= data['E']: # milliseconds since epoch
                    self.last_update_time = data['E']
                    changes = []
                    for price_str, qty_str in data.get('b', []):
                        changes.append(('buy', price_str, qty_str, self.last_update_time))
                    for price_str, qty_str in data.get('a', []):
                        changes.append(('sell', price_str, qty_str, self.last_update_time))

                    await self._process_l2update_fast(changes)
                else:
                    print(f"[{self.feed_name}] Warning: received out-of-order depth update (timestamp {data['E']} < last {self.last_update_time}). Ignoring.")
        except Exception as e:
            print(f"[{self.feed_name}] Depth processing error: {e}")

    # ----------------- Fast-Path Top-N -----------------
    async def _process_l2update_fast(self, changes: list[tuple[str, str, str, float]]):
        top_updated = False

        for side_str, price_str, size_str, dt in changes:
            price = float(price_str)
            size = float(size_str)
            side = 'bid' if side_str == 'buy' else 'ask'

            top_prices = self.book.bids_top_prices if side == 'bid' else self.book.asks_top_prices
            if price in top_prices or len(top_prices) < TOP_N or \
               (side == 'bid' and price > min(top_prices)) or \
               (side == 'ask' and price < max(top_prices)):
                old_top = self.book.get_top(side).copy()
                self.book.update_level(side, price, size, self.feed_name, dt)
                if self.book.get_top(side) != old_top:
                    top_updated = True

        # sanity checks
        iscrossed = self.book.bids_top_prices[0] >= self.book.asks_top_prices[0] if self.book.bids_top_prices and self.book.asks_top_prices else False
        if iscrossed:
            print(f"[{self.feed_name}] Error: book is crossed after top-N update. Best bid {max(self.book.get_top('bid'))}, best ask {min(self.book.get_top('ask'))}.")
            raise RuntimeError("Crossed internal book")
        
        if top_updated:
            await self._notify_book()

        # Phase 2: full book async
        for side_str, price_str, size_str, ts in changes:
            price = float(price_str)
            size = float(size_str)
            side = 'bid' if side_str == 'buy' else 'ask'
            self._full_book_queue.put_nowait((side, price, size, ts))