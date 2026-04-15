# Take-Home assignment – Simplified Async Multi-Feed Trading System

## Setup

# Note, this was set up on a ubuntu distribution, I have not tested it under windows

```bash
git clone <repo>
cd <repo>
python3 -m venv venv
source venv/bin/activate
pip install -e .
pip install -r requirements.txt

 ---

### Running the script:

python src/main.py

## Running Tests

pytest -v


---

## Overview

This project implements a real-time trading system that:

# Architecture:
  - 2 feed handlers that listen to feeds for BTC USD from binance and coinbase
  - 1 strategy object that subscribes to the feed handlers for callbacks on trades and book updates
  - on update strategy processes it and returns orders
  - main.py runs the process, and configs/config_strat_ben.py contains parameters

# Connects to multiple exchange feeds (e.g. Binance, Coinbase)
  - Processes market data asynchronously
  - Maintains internal state (orders, books, position, trades handling not implemented in this version, this should be a next step)
  - The internal books maintain a 20 lvl book on the fast path, which is what the strat cares for, but then maintain the full book on the slow path asynchronically
  - Monitors age of latest packet received top flag a stale quote, as well as feed status
  - On disconnect, will automatically reconnect and resume
  - Internal books are calculated only from updates on binance, but on coinbase we get a snapshot at connect so the book should be correct from the start.

# Fair value methodology
  - Strategy logic is triggered by callbacks from the feeds, on book updates and trades, returns desired orders
  - Computes derived signals (e.g. fair value)
  - The fair value here is calculated as a VWAP from a consolifated book across all feeds. 
    - We correct each quote for distance from mid, quote age, feed status
  - From here we determine quotes. This quotes around the fair value
    - We add a fixed spread from there, an input parameter
    - We add a position skew to favor reducing risk
    - We then try to dime the best bid by 1 tick if possible, else we place our quote at desired price, and join a level if necessary
    - Have not implemented logic accounting for largee quotes and holes in the book, which should be added also
    - Quote sizing 
      - Proportion of volumes seen on the top 20 levels, buffered to avoid replacing quotes too often
      - Last check vs position and max position parameter to avoid busting risk limits
  - Strategy tracks position from file src/position.json, you can simply modify this file and save and quotes will be adjusted accordingly. params max position is 1 so if you set position to +-1, you should see 

# Failure modes
  - Not sure what is asked here. In case of diconnected feed, the strategy simply ignores that feed and the feed tries to reconnect. Once it receives updates it will resume feeding them to the strategy. 

# Assumption made
  - I have not written any fill logic so no assumptions there
  - I don't think I have any other major assumptions

# Edge cases intentionally not handled
  - I have not implemented a volatility based quote adjustment, which I would
  - I assume infinite cash available on each exchange so have not implemented risk checks for that
  - I am not using trade information for pricing logic, this is a resource allocation decision
  - I am ignoring the insertion of my own orders in the internal book, but in reality I would remove them anyways because I do not want them to influence my pricing
  - I am ignoring large orders in the book and the quote adjustments I would make around them

# For production
  - see the assumptions above, I would have to further implement these
  - I woud have to implement the ordering to the API, then the handling of order status, fills, position from fills, etc
  - I would probably have to manage multiple coins in one strat, not just BTC, so that could be done by deploying multiple single coin algos or deploying it all in one algo, which might be preferential depending on if we want to manage cross coin risk

# sample output from live run
  - see screenshot.jpg. red lines are the active orders the strat is placing



* Provides a CLI monitoring interface
  - per feed, shows the top 20 levels with age of each quote, as well as age per feed

* Is testable with deterministic unit tests (only a handful of example tests are given, a production project would obviously need more thourough testinb)
* No detailed logging has been implemented, production version should log more details

---


The system will:

* connect to configured feeds
* process live data
* display state via CLI monitor


---

## Design Notes

### Async Architecture

* Uses `asyncio` for concurrency
* Each feed runs independently
* Strategy reacts to events on a tick by tick basis (if a packet of updates is given by the feed we treat them sequentially)

---

### Feed Design

Each feed:

* connects to exchange
* parses messages
* emits normalized events


---

### Strategy Design

* maintains internal state (position, orders)
* reacts to book updates, reacting to trades has not been implemented yet
* computes fair value
* computes desired orders

---
