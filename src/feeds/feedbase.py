class FeedBase:
    def __init__(self):
        self._book_listeners = []
        self._trade_listeners = []

    def subscribe_book(self, callback):
        """Callback signature: async def callback(feed_name: str, book: FeedOrderBook)"""
        self._book_listeners.append(callback)

    def subscribe_trade(self, callback):
        """Callback signature: async def callback(feed_name: str, trade: BookLevel)"""
        self._trade_listeners.append(callback)

    async def _notify_book(self):
        for cb in self._book_listeners:
            await cb(self.book_name, self.book)

    async def _notify_trade(self, trade):
        for cb in self._trade_listeners:
            await cb(self.book_name, trade)