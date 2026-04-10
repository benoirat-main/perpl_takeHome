"""
Author: Benjamin Noirat 
Date: 2026-04-06
"""

import pytest
from src.configs import config_strat_ben
from src.strategy.strat_ben import StratBen
from core.types import BookLevel

@pytest.mark.asyncio
async def test_load_position(strat):
    await strat.load_position()
    assert strat.position == 1


@pytest.mark.asyncio
async def test_load_position_missing_file(tmp_path):
    position_file = tmp_path / "missing.json"
    params = config_strat_ben.get_params()
    params['position_file'] = position_file
    strat = StratBen(params)
    await strat.load_position()

    await strat.load_position()

    # should not crash, should keep default
    assert hasattr(strat, "position")


@pytest.mark.asyncio
async def test_load_position_invalid_json(tmp_path):
    position_file = tmp_path / "bad.json"
    position_file.write_text("not json")

    params = config_strat_ben.get_params()
    params['position_file'] = position_file
    strat = StratBen(params)
    await strat.load_position()

    # should not crash
    assert hasattr(strat, "position")


@pytest.mark.asyncio
async def test_inv_distance_weighted_vwap (strat, get_test_time, mock_feed):
    await strat.load_position()

    strat.params['feeds'] = [mock_feed]
    # the logic uses machine time to determine time decay, we set half life to inf to avoid this dependency
    strat.params['fair_value']['quote_half_life_seconds'] = 999999999999999999999999

    bids = [
        BookLevel(side="bid", price=100.0, size=0.0123, exchange="mock_feed", last_update=get_test_time),
        BookLevel(side="bid", price=99.0, size=0.321, exchange="mock_feed", last_update=get_test_time)
    ]
    asks = [
        BookLevel(side="ask", price=101.0, size=0.0123, exchange="mock_feed", last_update=get_test_time),
        BookLevel(side="ask", price=103.0, size=0.123, exchange="mock_feed", last_update=get_test_time)
    ]
    bid_vwap, ask_vwap = strat.inv_distance_weighted_vwap(bids, asks)
    assert bid_vwap == 99.04935228705722
    assert ask_vwap == 102.66405981764774
    