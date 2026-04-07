"""
Author: Benjamin Noirat 
Date: 2026-04-02
"""

EPSILON = 1e-8

CONTRACT_SPECS = {
    "BTCUSD": {
        "binance": {
            "symbol": "BTCUSDT",
            "tick_size": 0.01,
            "min_qty": 0.0001,
        },
        "coinbase": {
            "symbol": "BTC-USD",
            "tick_size": 0.01,
            "min_qty": 0.00000001,
        },
    },
}