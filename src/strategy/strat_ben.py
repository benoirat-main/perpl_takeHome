
"""
Author: Benjamin Noirat 
Date: 2026-04-02
"""
from cmath import isclose
from core.constants import EPSILON, CONTRACT_SPECS

class StratBen:
    def __init__(self, params):
        # subscribe to all feeds
        self.params = params
        for feed in params['feeds']:
            feed.subscribe_book(self.on_book_update)
            feed.subscribe_trade(self.on_trade_update)
        self.position = 0.0
        self.active_orders = {}

    async def on_book_update(self, feed_name: str, book):
        if self.params['prints']['data_updates']:
            best_bid = book.get_best_bid()
            best_ask = book.get_best_ask()
            mid = book.get_mid()
            print(f"{feed_name} book: bid {best_bid}, ask {best_ask}, mid {mid}")

        # data sanity checks: mostly already implemented at the feed level
        

        # update indicators, in this exercise it is just the fair value
        fair_value = self.calc_global_fair_value()

        # produce orders from the fair value, the position management, the risk limits
        orders = self.calc_quotes(fair_value)

        # send out orders to markets
        self.send_orders(orders)

    def send_orders(self, orders_dict):
        # not implemented, as per assignment
        self.active_orders = orders_dict

    async def on_trade_update(self, feed_name: str, trade):
        if self.params['prints']['data_updates']:
            print(f"{feed_name} trade: {trade.size}@{trade.price}")

    def calc_global_fair_value(self):
        # aggregate books
        def consolidated_top_levels(nb_levels : int):
            # this will build a consilidated book accross all feeds, it will not filter for crossed bid-asks, as we might need all info later
            bids = []
            asks = []
            for feed in self.params['feeds']:
                bids.extend(feed.book.get_top('bid').values())  # list of BookLevel
                asks.extend(feed.book.get_top('ask').values())

            bids = sorted(bids, key=lambda x: x.price, reverse=True)[:nb_levels]
            asks = sorted(asks, key=lambda x: x.price)[:nb_levels]
            return {'bids': bids, 'asks': asks}
        
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
                    distance = abs(lvl.price - ref_px)
                    if isclose(distance, 0.0):
                        distance = EPSILON  # prevent divide by zero, although it should not happen if we uncrossed correcctly
                    weight       = lvl.size / distance
                    weighted_sum += lvl.price * weight
                    weight_total += weight
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

            # calc fair value as average of bid and ask weighted VWAPs
            bid_vwap, ask_vwap   = inv_distance_weighted_vwap(all_bids, all_asks)
            fair_value = (bid_vwap + ask_vwap) / 2 if bid_vwap is not None and ask_vwap is not None else None
        else:
            fair_value = None

        return fair_value
    
    def calc_quotes(self, fair_value):
        def apply_spread(fair_value):
            half_spread = self.params['quotes']['spread_fixed'] / 2
            size_bid    = min(self.params['quotes']['size'], self.params['risk_limits']['max_position'] - self.position)
            size_ask    = min(self.params['quotes']['size'], self.params['risk_limits']['max_position'] + self.position)
            bid_price   = fair_value - half_spread
            ask_price   = fair_value + half_spread
            return bid_price, ask_price, size_bid, size_ask
        
        def apply_position_spread(bid_price, ask_price):
            pos_skew  = (
                0.0 if self.params['risk_limits']['max_position'] == 0 else
                    self.position / self.params['risk_limits']['max_position'] * self.params['quotes']['spread_max_pos']
            )
            bid_price = max(bid_price - pos_skew, 0.0)
            ask_price = max(ask_price + pos_skew, 0.0)
            return bid_price, ask_price

        if fair_value is None:
            return {}
        else:
            bid_price, ask_price, size_bid, size_ask = apply_spread(fair_value)
            bid_price, ask_price = apply_position_spread(bid_price, ask_price)

            orders_dict = {}
            for feed in self.params['feeds']:
                # adapt quoting logic to each feed
                tick_size = CONTRACT_SPECS[self.params['symbol']][feed.feed_name]["tick_size"]
                bid_price = min(bid_price, feed.book.get_best_bid()[0] + tick_size * 1) if feed.book.get_best_bid() else bid_price
                ask_price = max(ask_price, feed.book.get_best_ask()[0] - tick_size * 1) if feed.book.get_best_ask() else ask_price

                orders_dict[feed.feed_name] = [
                        {'side': 'bid', 'price': bid_price, 'size': size_bid},
                        {'side': 'ask', 'price': ask_price, 'size': size_ask}
                    ]
            return orders_dict
