"""
Author: Benjamin Noirat 
Date: 2026-04-06
"""

import pytest
import json
from src.configs import config_strat_ben

@pytest.fixture
def get_test_time():
    return 1775803657855

@pytest.fixture
def sample_orders():
    from src.core.types import Order
    return [
        Order(exchange="binance", side="bid", price=100.0, size=1.0, ts_sent=get_test_time()),
        Order(exchange="binance", side="ask", price=101.0, size=2.0, ts_sent=get_test_time()),
    ]


@pytest.fixture
def position_file(tmp_path):
    file = tmp_path / "position.json"
    file.write_text(json.dumps({"position": 1}))
    return file


@pytest.fixture
def strat(position_file):
    from strategy.strat_ben import StratBen
    params = config_strat_ben.get_params()
    params['position_file'] = position_file
    strat = StratBen(params)
    return strat


class MockFeed:
    def __init__(self):
        self.feed_name = "mock_feed"
        self.connected = True

@pytest.fixture
def mock_feed():
    return MockFeed()