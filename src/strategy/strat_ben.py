
"""
Author: Benjamin Noirat 
Date: 2026-04-02
"""
from cmath import isclose
import json
from core.constants import EPSILON, CONTRACT_SPECS
from core.types import Order
from core.order_book import FeedOrderBook
import math
import time
import math

class StratBen:
    def __init__(self, params):
        # subscribe to all feeds
        self.params = params
        for feed in params['feeds']:
            feed.subscribe_book(self.on_book_update)
            feed.subscribe_trade(self.on_trade_update)
        self.position: float = 0.0
        self.active_orders: dict[str, list[Order]] = {}

    async def on_book_update(self, feed_name: str, book):
        if self.params['prints']['data_updates']:
            best_bid = book.get_best_bid()
            best_ask = book.get_best_ask()
            mid = book.get_mid()
            print(f"{feed_name} book: bid {best_bid}, ask {best_ask}, mid {mid}")

        # data sanity checks: mostly already implemented at the feed level
        

        # update indicators, in this exercise it is just the fair value
        fair_value: float = self.calc_global_fair_value()

        # produce orders from the fair value, the position management, the risk limits
        orders: dict[str, list[Order]] = self.calc_quotes(fair_value)

        # send out orders to markets
        self.send_orders(orders)

    def send_orders(self, orders_dict: dict[str, list[Order]]):
        # not implemented, as per assignment
        # here we just assume orders become active immediately, if there was a similar active order, we do not replace it (and thus keep its original timestamp)
        for feed_name, orders in orders_dict.items():
            for i, new_order in enumerate(orders):
                if feed_name in self.active_orders:
                    for active_order in self.active_orders[feed_name]:
                        if active_order.side == new_order.side and active_order.price == new_order.price and active_order.size == new_order.size:
                            orders[i] = active_order
        if self.params['prints']['orders']:
            for feed in self.params['feeds']:
                active_orders = self.active_orders[feed.feed_name] if feed.feed_name in self.active_orders else []
                new_orders = orders_dict[feed.feed_name]
                for active_order in active_orders:
                    if not any(all(getattr(active_order, attr) == getattr(new_order, attr) for attr in vars(active_order)) for new_order in new_orders):
                        print(f"Cancel {active_order} on {feed.feed_name}")
                for new_order in new_orders:
                    if not any(all(getattr(active_order, attr) == getattr(new_order, attr) for attr in vars(active_order)) for active_order in active_orders):
                        print(f"Send {new_order} on {feed.feed_name}")
        self.active_orders = orders_dict

    async def on_trade_update(self, feed_name: str, trade):
        # TODO: this can be used to improve prediction or fair value
        if self.params['prints']['data_updates']:
            print(f"{feed_name} trade: {trade.size}@{trade.price}")

    async def load_position(self):
        try:
            with open(self.params['position_file'], 'r') as f:
                data = json.load(f)
            self.position = data.get("position", self.position)
        except Exception as e:
            print(f"[red]Error reading position file:[/red] {e}")

    def calc_global_fair_value(self):
        # aggregate books
        def consolidated_top_levels(nb_levels : int):
            # this will build a consilidated book accross all feeds, it will not filter for crossed bid-asks, as we might need all info later
            bids = []
            asks = []
            for feed in self.params['feeds']:
                bids.extend(feed.book.get_top('bid').values())  # list of BookLevel
                asks.extend(feed.book.get_top('ask').values())

            bids_sorted = sorted(bids, key=lambda x: x.price, reverse=True)[:nb_levels]
            asks_sorted = sorted(asks, key=lambda x: x.price)[:nb_levels]
            return {'bids': bids_sorted, 'asks': asks_sorted}

        # calculate the VWAP of the consolidated top-N levels, weighted by inverse distance to mid, more robust to changes deeeper in the book
        def inv_distance_weighted_vwap(bids, asks):
            vwap_bids = (
                (sum(b.price * b.size for b in bids) / total) 
                if (total := sum(b.size for b in bids)) > 0 
                else None
            )
            vwap_asks = (
                (sum(a.price * a.size for a in asks) / total) 
                if (total := sum(a.size for a in asks)) > 0 
                else None
            )

            # now weigh eeach level, giving less weight to the ones further away. I use opposite VWAP as a ref price as using mid would put too much weight on the first level
            def get_inv_distance_weighted_vwap(levels, ref_px):
                weighted_sum = 0.0
                weight_total = 0.0
                for lvl in levels:
                    feed     = next((f for f in self.params['feeds'] if f.feed_name == lvl.exchange), None)
                    distance = max(abs(lvl.price - ref_px), EPSILON)
                    age_secs = time.time() - lvl.last_update / 1000

                    weight_distance = lvl.size / distance
                    weight_status   = 1.0 if feed.connected else 0.0
                    weight_freshness = math.exp(-math.log(2) * age_secs / self.params['fair_value']['quote_half_life_seconds'])
                    weight = weight_distance * weight_status * weight_freshness
                    
                    weighted_sum    += lvl.price * weight
                    weight_total    += weight
                return weighted_sum / weight_total if weight_total > 0 else None
            bid_vwap = get_inv_distance_weighted_vwap(bids, vwap_asks) if vwap_asks is not None else None
            ask_vwap = get_inv_distance_weighted_vwap(asks, vwap_bids) if vwap_bids is not None else None
            return bid_vwap, ask_vwap

        consolidated_book = consolidated_top_levels(self.params['fair_value']['top_n'])

        # uncross the consolidated book
        if consolidated_book['bids'] and consolidated_book['asks']:
            if self.params['fair_value']['uncross_consolidated_book']:
                min_ask  = min(x.price for x in consolidated_book['asks'])
                max_bid  = max(x.price for x in consolidated_book['bids'])
                all_bids = [lvl for lvl in consolidated_book['bids'] if lvl.price <= min_ask]
                all_asks = [lvl for lvl in consolidated_book['asks'] if lvl.price >= max_bid]
            else:
                all_bids = consolidated_book['bids']
                all_asks = consolidated_book['asks']
            # TODO: we might want to ignore our own active orders in the fair value calculation

            bid_vwap, ask_vwap   = inv_distance_weighted_vwap(all_bids, all_asks)
            fair_value = (bid_vwap + ask_vwap) / 2 if bid_vwap is not None and ask_vwap is not None else None
        else:
            fair_value = None

        return fair_value
    
    def calc_quotes(self, fair_value) -> dict[str, list[Order]]:
        def apply_spread(fair_value) -> tuple[float, float, float, float]:
            half_spread = self.params['quotes']['spread_fixed'] / 2
            bid_price   = fair_value - half_spread
            ask_price   = fair_value + half_spread
            return bid_price, ask_price
        
        def apply_position_spread(bid_price, ask_price) -> tuple[float, float]:
            pos_skew  = (
                0.0 if self.params['risk_limits']['max_position'] == 0 else
                    -self.position / self.params['risk_limits']['max_position'] * self.params['quotes']['spread_max_pos']
            )
            bid_price_pos = max(bid_price + pos_skew, 0.0)
            ask_price_pos = max(ask_price + pos_skew, 0.0)
            return bid_price_pos, ask_price_pos
        
        def avoid_large_whales(bid_price, ask_price) -> tuple[float, float]:
            return bid_price, ask_price

        def apply_sizing(ob: FeedOrderBook) -> tuple[float, float]:
            # this part could be written in a more efficient way, but this way is preferred for now as more readable

            def round_10pct(x: float) -> float:
                if x == 0:
                    return 0
                magnitude = 10 ** math.floor(math.log10(abs(x)))
                rounded = round(x / magnitude, 1) * magnitude
                return rounded

            # base size from config
            size_bid    = self.params['quotes']['size']
            size_ask    = self.params['quotes']['size']

            # adjust according to market siZe to avoid pushing the market. 
            # I decided to use both bid and ask, it could be that using a specific side works better
            vol_bid     = sum([lvl.size for _, lvl in ob.bids_top.items()])
            vol_ask     = sum([lvl.size for _, lvl in ob.asks_top.items()])
            vol_top_lvl = (vol_bid + vol_ask) / 2.0
            size_bid    = min(size_bid, vol_top_lvl * self.params['quotes']['max_share_mkt'])
            size_ask    = min(size_ask, vol_top_lvl * self.params['quotes']['max_share_mkt'])
            # round sizes to avoid re ordering constanlty
            size_bid = round_10pct(size_bid)
            size_ask = round_10pct(size_ask)

            # do not try to exceed max position limits
            size_bid    = min(size_bid, self.params['risk_limits']['max_position'] - self.position)
            size_ask    = min(size_ask, self.params['risk_limits']['max_position'] + self.position)

            # sanity check, no negative sizes
            size_bid    = max(0.0, size_bid)
            size_ask    = max(0.0, size_ask)
            return size_bid, size_ask

        if fair_value is None:
            return {}
        else:
            bid_price, ask_price = apply_spread(fair_value)
            bid_price, ask_price = apply_position_spread(bid_price, ask_price)
            bid_price, ask_price = avoid_large_whales(bid_price, ask_price)
            timestamp = time.time() * 1000 # milliseconds since epoch

            orders_dict = {}
            for feed in self.params['feeds']:
                # adapt quoting logic to each feed
                tick_size = CONTRACT_SPECS[self.params['symbol']][feed.feed_name]["tick_size"]

                # sizing
                size_bid, size_ask   = apply_sizing(feed.book)
                
                # dime the best quotee on our side
                bid_price = min(bid_price, feed.book.get_best_bid().price + tick_size * 1) if feed.book.get_best_bid() else bid_price
                ask_price = max(ask_price, feed.book.get_best_ask().price - tick_size * 1) if feed.book.get_best_ask() else ask_price
                
                # now explicitely forbid crossing the spread if diming were to make us aggreessivelly taking the other side
                bid_price = min(bid_price, feed.book.get_best_ask().price - tick_size * 1) if feed.book.get_best_ask() else bid_price
                ask_price = max(ask_price, feed.book.get_best_bid().price + tick_size * 1) if feed.book.get_best_bid() else ask_price

                orders_dict[feed.feed_name] = []
                if size_bid > EPSILON:
                    order = Order(feed.feed_name, 'bid', bid_price, size_bid, timestamp)
                    orders_dict[feed.feed_name].append(order)
                if size_ask > EPSILON:
                    order = Order(feed.feed_name, 'ask', ask_price, size_ask, timestamp)
                    orders_dict[feed.feed_name].append(order)
            return orders_dict
