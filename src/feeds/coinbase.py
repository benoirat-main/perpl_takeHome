"""
Author: Benjamin Noirat
Date: 2026-04-02
Updated: 2026-04-02
Top-N fast-path updates first, full book async after
"""

import asyncio
import json
import pdb
import sys
import websockets

from core.constants import EPSILON, CONTRACT_SPECS
from core.types import Trade
from core.order_book import TOP_N
from feeds.feedbase import FeedBase
from datetime import datetime

class CoinbaseFeed(FeedBase):
    def __init__(self, params):
        super().__init__(params)
        self.feed_name = "coinbase"
        self.symbol = CONTRACT_SPECS[self.params['symbol']][self.feed_name]["symbol"].upper()
        self.ws_url = "wss://ws-feed.exchange.coinbase.com"

    # ----------------- WebSocket Connection -----------------
    async def connect(self):
        while True:
            try:
                async with websockets.connect(self.ws_url, max_size=None) as ws:
                    await self._subscribe(ws)
                    self.connected = True
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
        try:
            async for msg in ws:
                data     = json.loads(msg)
                msg_type = data.get("type")
                msg_ts   = data.get("time")
                dt       = datetime.fromisoformat(msg_ts.replace("Z", "+00:00")).timestamp() * 1000 if msg_ts else 0.0

                if dt >= self.last_update_time:
                    if msg_type == "snapshot":
                        for side in ['bids', 'asks']:
                            for price_str, size_str in data[side]:
                                price = float(price_str)
                                size = float(size_str)
                                self.book.update_level(side[:-1], price, size, self.feed_name, dt)
                        await self._notify_book()
                    elif msg_type == "l2update":
                        dt_str = data.get("time")
                        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).timestamp() * 1000 # Convert to milliseconds since epoch
                        self.last_update_time = dt
                        changes = data.get("changes", [])
                        await self._process_l2update_fast(changes, dt)
                    elif msg_type == "match":
                        dt_str = data.get("time")
                        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).timestamp() * 1000 # Convert to milliseconds since epoch
                        if dt >= self.last_trade_time:
                            self.last_trade_time = dt                  
                            price = float(data['price'])
                            size = float(data['size'])
                            if size > EPSILON:
                                trade = Trade(price=price, size=size, exchange=self.feed_name, timestamp=dt)
                                await self._notify_trade(trade)
                else:
                    print(f"[{self.feed_name}] Warning: received out-of-order trade update (timestamp {dt} < last {self.last_trade_time}). Ignoring.")
        except Exception as e:
            print(f"[{self.feed_name}] Error processing message: {e}")
            pdb.post_mortem(sys.exc_info()[2])

    # ----------------- Fast-Path Top-N -----------------
    async def _process_l2update_fast(self, changes, dt):
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
                old_top = self.book.get_top(side).copy()
                self.book.update_level(side, price, size, self.feed_name, dt)
                if self.book.get_top(side) != old_top:
                    top_updated = True

        # sanity checks
        iscrossed = self.book.bids_top_prices[0] >= self.book.asks_top_prices[0] if self.book.bids_top_prices and self.book.asks_top_prices else False
        if iscrossed:
            print(f"[{self.feed_name}] Error: book is crossed after top-N update. Best bid {max(self.book.get_top('bid'))}, best ask {min(self.book.get_top('ask'))}.")
            raise RuntimeError("Crossed internal book")

        # Notify strategy immediately after top-N update
        if top_updated:
            await self._notify_book()

        # --- Phase 2: update full book asynchronously ---
        for side_str, price_str, size_str in changes:
            price = float(price_str)
            size = float(size_str)
            side = 'bid' if side_str == 'buy' else 'ask'
            # Push all changes to the queue for background processing
            self._full_book_queue.put_nowait((side, price, size, dt))