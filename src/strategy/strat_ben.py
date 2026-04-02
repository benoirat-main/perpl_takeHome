
class StratBen:
    def __init__(self, feeds):
        # subscribe to all feeds
        for feed in feeds:
            feed.subscribe_book(self.on_book_update)
            feed.subscribe_trade(self.on_trade_update)

    async def on_book_update(self, feed_name: str, book):
        best_bid = book.get_best_bid()
        best_ask = book.get_best_ask()
        mid = book.get_mid()
        print(f"{feed_name} book: bid {best_bid}, ask {best_ask}, mid {mid}")

    async def on_trade_update(self, feed_name: str, trade):
        print(f"{feed_name} trade: {trade.size}@{trade.price}")