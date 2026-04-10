# Perpl Take-Home – Async Multi-Feed Trading System

## Setup

# Note, this was set up on a ubuntu distribution, I have not tested it under windows

```bash
git clone <repo>
cd <repo>
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

* Connects to multiple exchange feeds (e.g. Binance, Coinbase)
  - Processes market data asynchronously
  - Maintains internal state (orders, books, position, trades handling not implemented in this version, this should be a next step)
  - The internal books maintain a 20 lvl book on the fast path, which is what the strat cares for, but then maintain the full book on the slow path asynchronically
  - Monitors age of latest packet received top flag a stale quote, as well as feed status
  - On disconnect, will automatically reconnect and resume

* Strategy logic is triggered by callbacks from the feeds, on book updates and trades, returns desired orders
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
  - Strategy tracks position from file position.json, you can simply modify this file and save and quotes will be adjusted accordingly

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